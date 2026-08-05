"""Execute DAGs produced by dam-workflow."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

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
            )
            model_id = self._node_model_id(node)
            if not model_id:
                output = {
                    "skipped": True,
                    "reason": "节点未配置 model_id，无法由模型库执行",
                    "inputs": inputs,
                }
                context[node_id] = output
                node_results.append(self._node_result(node, "skipped", output))
                continue

            request_data = self._build_request_data(node, inputs, prompt, sensor_data, event_type)
            try:
                infer_service = get_infer_service()
                if mode == "run":
                    output = infer_service.run(
                        db,
                        model_id,
                        request_data,
                        wait_timeout=wait_timeout,
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
                node_results.append(self._node_result(node, "success", normalized))
            except Exception as exc:
                output = {
                    "error": str(exc),
                    "model_id": model_id,
                    "inputs": inputs,
                }
                context[node_id] = output
                node_results.append(self._node_result(node, "failed", output))

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
        inputs.setdefault("images", images)
        inputs.setdefault("videos", videos)
        inputs.setdefault("media_objects", media_objects)
        inputs.setdefault("sensor_data", sensor_data)
        inputs.setdefault("user_prompt", prompt)
        inputs.setdefault("event_type", event_type)
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
        template = node.get("prompt_template") or node.get("evaluation_template")
        if template:
            return {
                "prompt": self._render_prompt(template, request_inputs, prompt, sensor_data, event_type),
                "inputs": request_inputs,
                **metadata,
            }
        return {**request_inputs, **metadata}

    @staticmethod
    def _node_request_metadata(node: Dict[str, Any]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for key in ("actor_name", "system_prompt", "system_prompt_source"):
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
    def _node_result(node: Dict[str, Any], status: str, output: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "node_id": node.get("node_id"),
            "node_class": node.get("node_class"),
            "node_type": node.get("node_type"),
            "model_id": WorkflowExecutorService._node_model_id(node),
            "model_name": node.get("model_name"),
            "status": status,
            "output": output,
        }

    @staticmethod
    def _execution_status(node_results: List[Dict[str, Any]]) -> str:
        if any(row["status"] == "failed" for row in node_results):
            return "failed"
        if any(row["status"] == "skipped" for row in node_results):
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
