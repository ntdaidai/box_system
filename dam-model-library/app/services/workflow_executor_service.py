"""Execute DAGs produced by dam-workflow."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings

REFERENCE_PATTERN = re.compile(r"^\{\{([^{}.]+)\.([^{}]+)\}\}$")


def get_infer_service():
    from app.services.infer_service import infer_service

    return infer_service


class WorkflowExecutorService:
    """Topological DAG executor backed by model-library inference APIs."""

    def execute(
        self,
        db: Session,
        *,
        dag: Dict[str, Any],
        prompt: str = "",
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        media_objects: Optional[List[Dict[str, Any]]] = None,
        sensor_data: Optional[Dict[str, Any]] = None,
        event_type: Optional[str] = None,
        media_mode: str = "auto",
        max_frames: int = 8,
        fallback_to_frames: bool = True,
        mode: str = "infer",
        validate: bool = False,
        filter_output: bool = False,
        wait_timeout: int = 600,
    ) -> Dict[str, Any]:
        images = images or []
        videos = videos or []
        media_objects = media_objects or []
        sensor_data = sensor_data or {}
        nodes = dag.get("nodes") or []
        edges = dag.get("edges") or []
        node_map = {node.get("node_id"): node for node in nodes if node.get("node_id")}
        order = self._topological_order(node_map, edges)
        context: Dict[str, Dict[str, Any]] = {}
        node_results: List[Dict[str, Any]] = []

        for node_id in order:
            node = node_map[node_id]
            node_class = str(node.get("node_class") or "").upper()

            if node_class == "START":
                output = {
                    "event_type": event_type,
                    "images": images,
                    "videos": videos,
                    "media_objects": media_objects,
                    "sensor_data": sensor_data,
                    "user_prompt": prompt,
                    "media_mode": media_mode,
                    "max_frames": max_frames,
                    "fallback_to_frames": fallback_to_frames,
                }
                context[node_id] = output
                node_results.append(self._node_result(node, "success", output))
                continue

            if node_class == "END":
                output = self._collect_end_output(node, edges, context)
                context[node_id] = output
                node_results.append(self._node_result(node, "success", output))
                continue

            inputs = self._build_node_inputs(
                node=node,
                edges=edges,
                context=context,
                prompt=prompt,
                images=images,
                videos=videos,
                media_objects=media_objects,
                sensor_data=sensor_data,
                event_type=event_type,
                media_mode=media_mode,
                max_frames=max_frames,
                fallback_to_frames=fallback_to_frames,
            )
            model_id = self._node_model_id(node)
            if not model_id:
                node_text = f"{node_id} {node.get('node_type') or ''}".lower()
                pass_through = "track" in node_text or "跟踪" in node_text
                output = {
                    "skipped": True,
                    "reason": "节点未配置 model_id，无法由模型库执行",
                    "pass_through": pass_through,
                    "inputs": inputs,
                    # Pass-through nodes, such as a temporarily unconfigured
                    # tracker, must not break visual evidence propagation.
                    "images": inputs.get("images") if isinstance(inputs.get("images"), list) else [],
                    "videos": inputs.get("videos") if isinstance(inputs.get("videos"), list) else [],
                    "media_objects": inputs.get("media_objects") if isinstance(inputs.get("media_objects"), list) else [],
                    "detection_results": inputs.get("detection_results") or inputs.get("sensor_data"),
                }
                context[node_id] = output
                node_results.append(self._node_result(node, "skipped", output, request_data=None))
                continue

            request_data = self._build_request_data(node, inputs, prompt, sensor_data, event_type)
            try:
                infer_service = get_infer_service()
                if mode == "run":
                    node_wait_timeout = self._node_wait_timeout(node, wait_timeout)
                    output = infer_service.run(
                        db,
                        model_id,
                        request_data,
                        wait_timeout=node_wait_timeout,
                        validate=validate,
                        filter_output=filter_output,
                    )
                else:
                    output = infer_service.infer(
                        db,
                        model_id,
                        request_data,
                        validate=validate,
                        filter_output=filter_output,
                    )
                normalized = self._normalize_output(output)
                context[node_id] = normalized
                node_results.append(self._node_result(node, "success", normalized, request_data=request_data))
            except Exception as exc:
                output = {
                    "error": str(exc),
                    "model_id": model_id,
                    "inputs": inputs,
                }
                context[node_id] = output
                node_results.append(self._node_result(node, "failed", output, request_data=request_data))

        final_output = self._final_output(node_results, context)
        status = self._execution_status(node_results)
        return {
            "status": status,
            "order": order,
            "node_results": node_results,
            "final_output": final_output,
        }

    @staticmethod
    def _topological_order(node_map: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
        indegree = {node_id: 0 for node_id in node_map}
        graph: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in node_map and target in node_map:
                graph[source].append(target)
                indegree[target] += 1
        queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
        order: List[str] = []
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for target in graph[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        return order if len(order) == len(node_map) else list(node_map.keys())

    def _build_node_inputs(
        self,
        *,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        context: Dict[str, Dict[str, Any]],
        prompt: str,
        images: List[str],
        videos: List[str],
        media_objects: List[Dict[str, Any]],
        sensor_data: Dict[str, Any],
        event_type: Optional[str],
        media_mode: str,
        max_frames: int,
        fallback_to_frames: bool,
    ) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        node_id = node.get("node_id")
        for edge in edges:
            if edge.get("target") != node_id:
                continue
            data_flow = edge.get("data_flow") or {}
            for key, template in (data_flow.get("inputs") or {}).items():
                inputs[key] = self._resolve_value(template, context)
            source = edge.get("source")
            if source in context and not data_flow.get("inputs"):
                inputs[source] = context[source]
            if source in context:
                propagated_media = self._extract_media_objects(context[source])
                if propagated_media:
                    inputs["media_objects"] = propagated_media
                    propagated_videos = self._media_paths_by_type(propagated_media, "video")
                    propagated_images = self._media_paths_by_type(propagated_media, "image")
                    if propagated_videos:
                        inputs["videos"] = propagated_videos
                    if propagated_images:
                        inputs["images"] = propagated_images
                # Preserve edge-node knowledge retrieval results even when a
                # generated DAG only maps final_report to the cloud node.
                source_output = context[source]
                for key in (
                    "knowledge_context",
                    "knowledge_sources",
                    "knowledge_sources_summary",
                    "knowledge_query",
                ):
                    value = self._find_first_value(source_output, (key,))
                    if value not in (None, "", [], {}):
                        inputs.setdefault(key, value)
        inputs.setdefault("images", images)
        inputs.setdefault("videos", videos)
        inputs.setdefault("media_objects", media_objects)
        inputs.setdefault("sensor_data", sensor_data)
        inputs.setdefault("user_prompt", prompt)
        inputs.setdefault("event_type", event_type)
        inputs.setdefault("media_mode", media_mode)
        inputs.setdefault("max_frames", max_frames)
        inputs.setdefault("fallback_to_frames", fallback_to_frames)
        return inputs

    def _collect_end_output(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        context: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        data_flow = node.get("data_flow") or {}
        for key, template in (data_flow.get("inputs") or {}).items():
            output[key] = self._resolve_value(template, context)
        if output:
            return output
        for edge in edges:
            if edge.get("target") == node.get("node_id") and edge.get("source") in context:
                output[edge["source"]] = context[edge["source"]]
        return output

    @staticmethod
    def _resolve_value(template: Any, context: Dict[str, Dict[str, Any]]) -> Any:
        if not isinstance(template, str):
            return template
        match = REFERENCE_PATTERN.match(template.strip())
        if not match:
            return template
        node_id, field = match.groups()
        value = context.get(node_id, {})
        if field in value:
            return value[field]
        data = value.get("data")
        if isinstance(data, dict) and field in data:
            return data[field]
        result = value.get("inference_result")
        if isinstance(result, dict) and field in result:
            return result[field]
        return value.get("response", value)

    @staticmethod
    def _extract_media_objects(output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prefer cloud media refs produced by an upstream edge model."""
        if not isinstance(output, dict):
            return []
        candidates = [
            output.get("cloud_media_objects"),
            output.get("uploaded_media_objects"),
            output.get("media_objects"),
        ]
        data = output.get("data")
        if isinstance(data, dict):
            candidates.extend([
                data.get("cloud_media_objects"),
                data.get("uploaded_media_objects"),
                data.get("media_objects"),
            ])
        nested_inputs = output.get("inputs")
        if isinstance(nested_inputs, dict):
            candidates.extend([
                nested_inputs.get("cloud_media_objects"),
                nested_inputs.get("uploaded_media_objects"),
                nested_inputs.get("media_objects"),
            ])
        result = output.get("inference_result")
        if isinstance(result, dict):
            candidates.extend([
                result.get("cloud_media_objects"),
                result.get("uploaded_media_objects"),
                result.get("media_objects"),
            ])
        for candidate in candidates:
            if isinstance(candidate, list) and candidate:
                return [item for item in candidate if isinstance(item, dict)]
        return []

    @staticmethod
    def _media_paths_by_type(media_objects: List[Dict[str, Any]], media_type: str) -> List[str]:
        paths: List[str] = []
        for item in media_objects:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or item.get("media_type") or "").lower()
            if item_type != media_type:
                continue
            ref = (
                item.get("path")
                or item.get("url")
                or item.get("minio_url")
                or item.get("file_url")
            )
            if not ref and item.get("bucket") and (item.get("object_key") or item.get("object_name")):
                ref = f"{item.get('bucket')}/{item.get('object_key') or item.get('object_name')}"
            if isinstance(ref, str) and ref:
                paths.append(ref)
        return paths

    def _build_request_data(
        self,
        node: Dict[str, Any],
        inputs: Dict[str, Any],
        prompt: str,
        sensor_data: Dict[str, Any],
        event_type: Optional[str],
    ) -> Dict[str, Any]:
        metadata = self._node_request_metadata(node)
        request_inputs = {**inputs, **metadata} if metadata else inputs
        media_options = self._media_options(node, request_inputs)
        if str(node.get("model_category") or "").lower() == "cloud_llm":
            return self._build_cloud_llm_request(
                node=node,
                inputs=request_inputs,
                sensor_data=sensor_data,
                event_type=event_type,
                media_options=media_options,
                metadata=metadata,
            )
        template = node.get("prompt_template") or node.get("evaluation_template")
        if template:
            compact_inputs = self._compact_for_prompt(request_inputs)
            top_media_objects = self._top_level_media_objects(node, request_inputs)
            model_category = str(node.get("model_category") or "").lower()
            request_data = {
                "prompt": self._render_prompt(
                    template,
                    compact_inputs,
                    self._short_text(prompt, 1200),
                    self._compact_for_prompt(sensor_data),
                    event_type,
                ),
                "inputs": compact_inputs,
                "sensor_data": sensor_data or request_inputs.get("sensor_data") or {},
                "event_type": event_type or request_inputs.get("event_type"),
                "images": request_inputs.get("images") or [],
                "videos": request_inputs.get("videos") or [],
                "media_objects": top_media_objects,
                **media_options,
                **metadata,
            }
            if model_category == "local_llm":
                request_data.setdefault("enable_knowledge_retrieval", True)
                # The cloud reviewer reads the original event video from the
                # cloud MinIO. Keep the 4B result local, but upload its source
                # media so the downstream 35B node does not receive only edge
                # review frames.
                request_data.setdefault("upload_media_to_cloud", True)
                request_data.setdefault(
                    "knowledge_query",
                    self._build_knowledge_query(prompt, event_type, sensor_data, request_inputs),
                )
                request_data.setdefault("request_timeout", max(1, int(settings.workflow_local_llm_node_timeout or 60)))
            return request_data
        return {**request_inputs, **media_options, **metadata}

    @staticmethod
    def _build_knowledge_query(
        prompt: str,
        event_type: Optional[str],
        sensor_data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> str:
        """Build a stable DAM knowledge retrieval query for local LLM nodes."""
        sensor_data = sensor_data if isinstance(sensor_data, dict) else {}
        inputs = inputs if isinstance(inputs, dict) else {}
        nested_sensor = inputs.get("sensor_data") if isinstance(inputs.get("sensor_data"), dict) else {}
        parts = [
            event_type,
            inputs.get("event_type"),
            sensor_data.get("event_name"),
            nested_sensor.get("event_name"),
            sensor_data.get("event_category"),
            nested_sensor.get("event_category"),
            sensor_data.get("summary"),
            nested_sensor.get("summary"),
            WorkflowExecutorService._compact_for_prompt(
                sensor_data.get("supplemental_context") or nested_sensor.get("supplemental_context") or {}
            ),
            WorkflowExecutorService._compact_for_prompt(
                sensor_data.get("risk_escalation") or nested_sensor.get("risk_escalation") or {}
            ),
            prompt,
        ]
        text = " ".join(str(item).strip() for item in parts if str(item or "").strip())
        return f"{text} 库坝巡查 处置规范 风险研判 应急处置".strip()

    @staticmethod
    def _top_level_media_objects(node: Dict[str, Any], inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """LLM 节点只把主视频证据放到顶层，避免中间抽帧淹没请求。"""
        objects = inputs.get("media_objects")
        objects = objects if isinstance(objects, list) else []
        model_category = str(node.get("model_category") or "").lower()
        if model_category in {"local_llm", "cloud_llm"}:
            videos = [item for item in objects if isinstance(item, dict) and str(item.get("type") or "").lower() == "video"]
            if videos:
                return videos[:2]
            video_paths = inputs.get("videos")
            video_paths = video_paths if isinstance(video_paths, list) else []
            return [{"type": "video", "path": path} for path in video_paths[:2] if isinstance(path, str) and path]
        return [item for item in objects if isinstance(item, dict)]

    @classmethod
    def _build_cloud_llm_request(
        cls,
        *,
        node: Dict[str, Any],
        inputs: Dict[str, Any],
        sensor_data: Dict[str, Any],
        event_type: Optional[str],
        media_options: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        cloud_media = cls._find_first_list(
            inputs,
            ("cloud_media_objects", "uploaded_media_objects"),
        )
        if not cloud_media:
            cloud_media = cls._extract_media_objects(inputs)

        # The cloud service should perform video understanding from one
        # authoritative object. Sending the annotated YOLO video together
        # with the raw video and eight edge frames can overload the remote
        # multimodal request and makes the service disconnect. Prefer the
        # annotated downstream video, then fall back to the first video.
        video_objects = [
            item for item in cloud_media
            if isinstance(item, dict)
            and str(item.get("type") or item.get("media_type") or "").lower() == "video"
        ]
        if video_objects:
            annotated = [
                item for item in video_objects
                if "annotated" in str(item.get("source") or "").lower()
                or "annotated" in str(item.get("object_name") or "").lower()
                or str(item.get("role") or "").lower() == "annotated_detection_video"
            ]
            cloud_media = [annotated[0] if annotated else video_objects[0]]

        edge_analysis = (
            inputs.get("edge_analysis")
            or inputs.get("final_report")
            or inputs.get("report")
            or {}
        )
        # Keep the knowledge retrieved by the 4B edge node in the cloud
        # request. The final reviewer must use the same evidence basis.
        knowledge_context = cls._find_first_value(
            (inputs, edge_analysis, sensor_data),
            ("knowledge_context",),
        )
        knowledge_sources = cls._find_first_value(
            (inputs, edge_analysis, sensor_data),
            ("knowledge_sources",),
        )
        knowledge_summary = cls._find_first_value(
            (inputs, edge_analysis, sensor_data),
            ("knowledge_sources_summary",),
        )
        knowledge_query = cls._find_first_value(
            (inputs, edge_analysis, sensor_data),
            ("knowledge_query",),
        )
        preliminary_report = (
            inputs.get("preliminary_report")
            or inputs.get("analysis_report")
            or cls._extract_report_text(edge_analysis)
        )
        slim_sensor_data = cls._slim_sensor_data(sensor_data or inputs.get("sensor_data") or {})
        slim_inputs = {
            "event_type": event_type or inputs.get("event_type") or slim_sensor_data.get("event_name"),
            "preliminary_report": cls._short_text(preliminary_report, 1200),
            "edge_analysis": cls._compact_for_prompt(edge_analysis),
            "cloud_media_objects": cloud_media,
        }
        if knowledge_context:
            slim_inputs["knowledge_context"] = cls._compact_for_prompt(knowledge_context)
        if knowledge_sources:
            slim_inputs["knowledge_sources"] = cls._compact_for_prompt(knowledge_sources)
        if knowledge_summary:
            slim_inputs["knowledge_sources_summary"] = cls._short_text(knowledge_summary, 2400)
        if knowledge_query:
            slim_inputs["knowledge_query"] = cls._short_text(knowledge_query, 800)
        # 35B has the larger context window and must independently review the
        # complete retrieval result, not only a short 4B citation summary.
        # Keep source identity plus full clause content while omitting only
        # transport-only URLs and embedding metadata.
        full_results = []
        raw_results = knowledge_context.get("results") if isinstance(knowledge_context, dict) else []
        for item in raw_results if isinstance(raw_results, list) else []:
            if not isinstance(item, dict):
                continue
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            full_results.append({
                "evidence_id": item.get("evidence_id") or source.get("evidence_id"),
                "document_id": item.get("document_id") or source.get("document_id"),
                "document_title": source.get("document_title") or item.get("document_title"),
                "section_path": source.get("section_path") or item.get("section_path"),
                "clause_id": source.get("clause_id") or item.get("clause_id"),
                "score": item.get("score"),
                "content": item.get("content") or item.get("quote") or source.get("quote"),
                "metadata": item.get("metadata") or {},
            })
        # Restore the complete clause list after generic prompt compaction.
        # Keep only fields useful for reasoning; do not send transport URLs or
        # embedding metadata. The cloud service renders this object once in
        # its canonical event-report prompt.
        if isinstance(knowledge_context, dict):
            slim_inputs["knowledge_context"] = {
                "query": knowledge_context.get("query") or knowledge_query,
                "total": knowledge_context.get("total", len(full_results)),
                "results": full_results,
            }
        # Do not append the same full JSON to the node prompt as well,
        # otherwise the model sees duplicate clauses and competing output
        # instructions.
        prompt = (
            "请对本次库坝安全事件进行云端最终复核，并生成事件处置报告 JSON。"
            "只允许输出一个合法 JSON 对象，不要输出思考过程、解释文字、Markdown 代码块或 <think> 内容。"
            "以视频证据和边缘侧 4B 初判为主，不要虚构时间、地点、人员或设备动作；"
            "发生时间、事件编号等以传入的 sensor_data 为准。"
            "必须完整阅读输入中的知识库检索结果，将适用条款作为风险判断和处置建议的约束条件；"
            "只引用输入中提供的 evidence_id/clause_id，不得虚构条款。"
        )
        return {
            "prompt": prompt,
            "inputs": slim_inputs,
            "sensor_data": slim_sensor_data,
            "event_type": slim_inputs["event_type"],
            "images": [],
            "videos": [],
            "media_objects": cloud_media,
            "knowledge_context": knowledge_context or {},
            "knowledge_sources": knowledge_sources or [],
            "knowledge_sources_summary": knowledge_summary or "",
            "knowledge_query": knowledge_query or "",
            "report_requirement": {
                "format": "dam_workflow",
                "require_fields": ["report", "risk_level", "recommendations", "template_data"],
            },
            "request_timeout": max(1, int(settings.workflow_cloud_node_timeout or 30)),
            "media_mode": "video",
            "max_frames": 1,
            "fallback_to_frames": True,
            **{key: value for key, value in media_options.items() if key not in {"media_mode", "max_frames"}},
            **metadata,
        }

    @staticmethod
    def _find_first_value(values: Any, keys: tuple[str, ...]) -> Any:
        """Find a knowledge field in the current node or nested 4B output."""
        if isinstance(values, dict):
            for key in keys:
                if values.get(key) not in (None, "", [], {}):
                    return values[key]
            for item in values.values():
                found = WorkflowExecutorService._find_first_value(item, keys)
                if found not in (None, "", [], {}):
                    return found
        elif isinstance(values, (list, tuple)):
            for item in values:
                found = WorkflowExecutorService._find_first_value(item, keys)
                if found not in (None, "", [], {}):
                    return found
        return None

    @staticmethod
    def _node_wait_timeout(node: Dict[str, Any], default_timeout: int) -> int:
        model_category = str(node.get("model_category") or "").lower()
        if model_category == "cloud_llm":
            return max(1, int(settings.workflow_cloud_node_timeout or 30))
        if model_category == "local_llm":
            return max(1, int(settings.workflow_local_llm_node_timeout or 60))
        return int(default_timeout or 600)

    @staticmethod
    def _find_first_list(value: Any, keys: tuple[str, ...]) -> List[Dict[str, Any]]:
        if isinstance(value, dict):
            for key in keys:
                candidate = value.get(key)
                if isinstance(candidate, list) and candidate:
                    return [item for item in candidate if isinstance(item, dict)]
            for item in value.values():
                found = WorkflowExecutorService._find_first_list(item, keys)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = WorkflowExecutorService._find_first_list(item, keys)
                if found:
                    return found
        return []

    @staticmethod
    def _extract_report_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("analysis_report", "report", "scene_analysis", "response"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    return item
                if isinstance(item, dict):
                    nested = WorkflowExecutorService._extract_report_text(item)
                    if nested:
                        return nested
        return ""

    @staticmethod
    def _slim_sensor_data(sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(sensor_data, dict):
            return {}
        keep = (
            "event_id",
            "event_code",
            "event_name",
            "event_category",
            "event_instance_no",
            "instance_no",
            "risk_level",
            "qwen_summary",
            "qwen_risk_level",
            "camera_id",
            "camera_name",
            "started_at",
            "create_time",
            "occur_time",
            "flood_detected",
            "flood_confidence",
            "mudslide_detected",
            "mudslide_confidence",
            "landslide_detected",
            "landslide_confidence",
            "earthquake_detected",
            "earthquake_confidence",
            "person_present",
            "person_confidence",
            "boat_present",
            "boat_confidence",
            "possible_person",
            "possible_boat",
            "supplemental_context",
            "risk_escalation",
        )
        return {key: sensor_data[key] for key in keep if key in sensor_data}

    @staticmethod
    def _media_options(node: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        requested_mode = str(inputs.get("media_mode") or "auto").lower()
        node_mode = str(node.get("media_mode") or "").lower()
        if node_mode in {"video", "frames", "auto"}:
            media_mode = node_mode
        elif requested_mode == "auto":
            media_mode = "video" if WorkflowExecutorService._node_prefers_video(node) else "frames"
        elif requested_mode in {"video", "frames"}:
            media_mode = requested_mode
        else:
            media_mode = "frames"
        return {
            "media_mode": media_mode,
            "max_frames": inputs.get("max_frames") or 8,
            "fallback_to_frames": inputs.get("fallback_to_frames", True),
            "read_media": inputs.get("read_media", True),
            "strict_media": inputs.get("strict_media", True),
        }

    @staticmethod
    def _node_prefers_video(node: Dict[str, Any]) -> bool:
        model_category = str(node.get("model_category") or "").lower()
        model_task = str(node.get("model_task") or node.get("node_type") or "").lower()
        model_family = str(node.get("model_family") or "").lower()
        node_text = " ".join(
            str(node.get(key) or "")
            for key in ("node_id", "node_type", "model_name", "model_task", "model_family", "model_category")
        ).lower()
        if model_category in {"local_llm", "cloud_llm"}:
            return True
        if model_task in {"scene_understanding", "behavior_understanding", "risk_fusion", "final_review"}:
            return True
        if "qwen" in model_family or "qwen" in node_text:
            return True
        return False

    @staticmethod
    def _node_request_metadata(node: Dict[str, Any]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for key in (
            "actor_name",
            "system_prompt",
            "system_prompt_source",
            "stage_code",
            "prompt_version",
            "prompt_model_scope",
            "model_task",
            "model_family",
            "event_group",
            "target_event_type",
            "confidence_policy",
        ):
            value = node.get(key)
            if value:
                metadata[key] = value
        return metadata

    @staticmethod
    def _render_prompt(
        template: str,
        inputs: Dict[str, Any],
        prompt: str,
        sensor_data: Dict[str, Any],
        event_type: Optional[str],
    ) -> str:
        values = {
            **inputs,
            "user_prompt": prompt,
            "sensor_data": sensor_data,
            "event_type": event_type,
            "detection_results": inputs.get("detection_results") or inputs,
            "preliminary_report": inputs.get("preliminary_report") or inputs.get("report") or inputs,
        }
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(
                "{{" + key + "}}",
                json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value),
            )
        return rendered

    @classmethod
    def _compact_for_prompt(cls, value: Any, depth: int = 0) -> Any:
        if depth > 3:
            return cls._summarize_leaf(value)
        if isinstance(value, dict):
            compact: Dict[str, Any] = {}
            if cls._looks_like_media_object(value):
                return cls._compact_media_object(value)
            priority = (
                "event_type",
                "event_name",
                "event_code",
                "risk_level",
                "qwen_summary",
                "qwen_risk_level",
                "summary",
                "class",
                "class_name",
                "confidence",
                "score",
                "status",
                "error",
                "response",
                "report",
                "final_report",
                "source_video_url",
                "videos",
                "media_objects",
                "frames",
                "key_frames",
            )
            for key in priority:
                if key in value:
                    compact[key] = cls._compact_for_prompt(value[key], depth + 1)
            for key, item in value.items():
                if key in compact or key in {"inputs", "user_prompt", "sensor_data"}:
                    continue
                if len(compact) >= 16:
                    break
                compact[key] = cls._compact_for_prompt(item, depth + 1)
            return compact
        if isinstance(value, list):
            if value and all(isinstance(item, dict) and cls._looks_like_media_object(item) for item in value):
                return [cls._compact_media_object(item) for item in value[:2]]
            items = [cls._compact_for_prompt(item, depth + 1) for item in value[:6]]
            if len(value) > 6:
                items.append({"omitted_count": len(value) - 6})
            return items
        if isinstance(value, str):
            if cls._looks_like_media_ref(value):
                return cls._compact_media_ref(value)
            return cls._short_text(value, 800)
        return value

    @staticmethod
    def _looks_like_media_object(value: Dict[str, Any]) -> bool:
        keys = {"path", "url", "object_name", "object_key", "bucket", "type"}
        return bool(keys.intersection(value.keys()))

    @staticmethod
    def _compact_media_object(value: Dict[str, Any]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {"type": value.get("type") or "media"}
        for key in ("bucket", "object_name", "object_key", "path", "url", "source", "content_type"):
            item = value.get(key)
            if item:
                compact[key] = item
        return compact

    @staticmethod
    def _looks_like_media_ref(value: str) -> bool:
        lowered = value.lower()
        return lowered.startswith(("http://", "https://", "minio://", "s3://")) or any(
            lowered.endswith(suffix)
            for suffix in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".mov", ".webm", ".avi", ".mkv")
        )

    @staticmethod
    def _compact_media_ref(value: str) -> str:
        text = str(value or "")
        if "/" not in text:
            return WorkflowExecutorService._short_text(text, 96)
        parts = text.rstrip("/").split("/")
        tail = "/".join(parts[-3:])
        return WorkflowExecutorService._short_text(tail, 120)

    @staticmethod
    def _summarize_leaf(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "size": len(value)}
        if isinstance(value, str):
            return WorkflowExecutorService._short_text(value, 200)
        return value

    @staticmethod
    def _short_text(value: str, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[:limit] + f"...[truncated {len(text) - limit} chars]"

    @staticmethod
    def _node_model_id(node: Dict[str, Any]) -> Optional[int]:
        model_id = node.get("model_id")
        if model_id is None:
            model_id = (node.get("implementation") or {}).get("model_id")
        try:
            return int(model_id) if model_id is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_output(output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(output, dict):
            return {"data": output}
        data = output.get("inference_result") if isinstance(output.get("inference_result"), dict) else output
        choices = data.get("choices") or data.get("data", {}).get("choices") if isinstance(data, dict) else None
        if choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            content = (first.get("message") or {}).get("content") or first.get("text")
            if content:
                data.setdefault("response", content)
                data.setdefault("report", content)
        return output if "inference_result" in output else data

    @staticmethod
    def _node_result(
        node: Dict[str, Any],
        status: str,
        output: Dict[str, Any],
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "node_id": node.get("node_id"),
            "node_class": node.get("node_class"),
            "node_type": node.get("node_type"),
            "model_id": WorkflowExecutorService._node_model_id(node),
            "model_name": node.get("model_name"),
            "status": status,
            "request_meta": WorkflowExecutorService._request_meta(request_data or {}),
            "output": output,
        }

    @staticmethod
    def _request_meta(request_data: Dict[str, Any]) -> Dict[str, Any]:
        videos = request_data.get("videos")
        images = request_data.get("images")
        media_objects = request_data.get("media_objects")
        videos = videos if isinstance(videos, list) else []
        images = images if isinstance(images, list) else []
        media_objects = media_objects if isinstance(media_objects, list) else []
        return {
            "media_mode": request_data.get("media_mode"),
            "fallback_to_frames": request_data.get("fallback_to_frames"),
            "max_frames": request_data.get("max_frames"),
            "image_count": len(images),
            "video_count": len(videos),
            "media_object_count": len(media_objects),
            "video_object_count": sum(
                1 for item in media_objects
                if isinstance(item, dict) and str(item.get("type") or "").lower() == "video"
            ),
        }

    @staticmethod
    def _execution_status(node_results: List[Dict[str, Any]]) -> str:
        if any(row["status"] == "failed" for row in node_results):
            return "failed"
        if any(
            row["status"] == "skipped"
            and not (isinstance(row.get("output"), dict) and row["output"].get("pass_through"))
            for row in node_results
        ):
            return "partial"
        return "success"

    @staticmethod
    def _final_output(
        node_results: List[Dict[str, Any]],
        context: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        if "end_0" in context:
            output = context["end_0"]
        else:
            output = node_results[-1]["output"] if node_results else {}
        if not isinstance(output, dict):
            output = {"data": output}

        fallback = WorkflowExecutorService._latest_template_output(node_results)
        if fallback and not WorkflowExecutorService._contains_template_output(output):
            output = {
                **output,
                "fallback_output": fallback,
                "template_id": fallback.get("template_id"),
                "template_data": fallback.get("template_data") or fallback.get("docx_context"),
                "template_fields": fallback.get("template_fields"),
                "template_tables": fallback.get("template_tables"),
                "docx_context": fallback.get("docx_context") or fallback.get("template_data"),
                "result_source": fallback.get("result_source") or "workflow_fallback",
            }
        return output

    @staticmethod
    def _contains_template_output(output: Dict[str, Any]) -> bool:
        if not isinstance(output, dict):
            return False
        if output.get("template_data") or output.get("docx_context"):
            return True
        for value in output.values():
            if isinstance(value, dict) and (value.get("template_data") or value.get("docx_context")):
                return True
        return False

    @staticmethod
    def _latest_template_output(node_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        for row in reversed(node_results):
            if row.get("status") != "success":
                continue
            output = row.get("output")
            if isinstance(output, dict) and (output.get("template_data") or output.get("docx_context")):
                return output
        return {}


workflow_executor_service = WorkflowExecutorService()
