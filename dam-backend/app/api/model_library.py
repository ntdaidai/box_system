"""User-facing model library APIs."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from typing import Any, Optional
from pathlib import PurePosixPath, Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, Query, UploadFile
from loguru import logger

from app.services.dam_model_library_client import dam_model_library_client


router = APIRouter()


STATUS_LABELS = {
    "running": "可用",
    "building": "构建中",
    "starting": "启动中",
    "stopping": "停止中",
    "stopped": "未运行",
    "error": "异常",
}

STATUS_LEVELS = {
    "running": "success",
    "building": "warning",
    "starting": "warning",
    "stopping": "warning",
    "stopped": "info",
    "error": "danger",
}

IMPORT_ROOT = Path("/app/data/model-imports")
try:
    IMPORT_OWNER_UID = int(os.getenv("MODEL_IMPORT_OWNER_UID", "1000"))
    IMPORT_OWNER_GID = int(os.getenv("MODEL_IMPORT_OWNER_GID", "1000"))
except ValueError:
    IMPORT_OWNER_UID = 1000
    IMPORT_OWNER_GID = 1000


def _restore_import_ownership(target_dir: Path) -> None:
    """让宿主机用户可以继续编辑通过容器导入的目录。"""
    for root, directories, files in os.walk(target_dir):
        for name in [root, *directories, *files]:
            try:
                os.chown(os.path.join(root, name) if name != root else root, IMPORT_OWNER_UID, IMPORT_OWNER_GID)
            except (OSError, PermissionError) as exc:
                logger.warning("导入文件权限修复失败: path={}, error={}", name, exc)


def _safe_relative_path(filename: str) -> str:
    path = PurePosixPath(str(filename or "").replace("\\", "/"))
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"非法文件路径: {filename}")
    return "/".join(parts)


def _strip_root(path: str, root: str) -> str:
    return path[len(root) + 1 :] if root and path.startswith(f"{root}/") else path


def _format_size(value: int) -> str:
    if value <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = float(value)
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}" if index else f"{int(size)} {units[index]}"


def _extract_compose_value(text: str, key: str) -> str:
    matched = re.search(rf"\b{re.escape(key)}:\s*[\"']?([^\"'\n]+)", text or "", re.I)
    return matched.group(1).strip() if matched else ""


def _extract_compose_port(text: str) -> tuple[Optional[int], Optional[int]]:
    matched = re.search(r"-\s*[\"']?(\d{2,5}):(\d{2,5})", text or "")
    if not matched:
        return None, None
    return int(matched.group(1)), int(matched.group(2))


def _extract_compose_environment(text: str) -> dict[str, str]:
    """解析 Compose 中常见的 environment 列表/映射写法。"""
    matched = re.search(r"(?m)^(?P<indent>[ \t]*)environment:\s*$", text or "")
    if not matched:
        return {}

    base_indent = len(matched.group("indent").expandtabs(2))
    environment: dict[str, str] = {}
    for line in text[matched.end():].splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if indent <= base_indent:
            break
        value = line.strip()
        if value.startswith("-"):
            value = value[1:].strip()
            if "=" not in value:
                continue
            key, item = value.split("=", 1)
        elif ":" in value:
            key, item = value.split(":", 1)
        else:
            continue
        key = key.strip().strip("\"'")
        item = item.strip().strip("\"'")
        if key:
            environment[key] = item
    return environment


def _extract_compose_network_name(text: str) -> str:
    matched = re.search(
        r"(?m)^networks:\s*\n[ \t]+(?P<name>[a-zA-Z0-9_.-]+):\s*$",
        text or "",
    )
    return matched.group("name") if matched else "bridge"


def _infer_health_check(paths: list[str], readme_text: str) -> str:
    text = f"{' '.join(paths)} {readme_text}".lower()
    if "/healthz" in text:
        return "/healthz"
    if "/health" in text:
        return "/health"
    return ""


def _extract_service_name(text: str) -> str:
    matched = re.search(r"^ {2}([a-zA-Z0-9_.-]+):\s*$", text or "", re.M)
    return matched.group(1) if matched else ""


def _coerce_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _default_import_image_name(folder_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", folder_name.strip().lower()).strip("-")
    return f"dam-import/{normalized or 'model'}:latest"


def _infer_import_capability(folder_name: str, paths: list[str], compose_text: str, readme_text: str) -> str:
    text = f"{folder_name} {' '.join(paths)} {compose_text} {readme_text}".lower()
    if "vllm_base_url" in text or "qwen" in text:
        return "视觉语言模型"
    if "-od" in text or "detector" in text or "detect/image" in text:
        return "目标检测"
    if "-cls" in text or "classifier" in text or "yolo_service" in text:
        return "图像分类"
    return "通用服务"


def _infer_import_architecture(folder_name: str, paths: list[str], compose_text: str) -> str:
    text = f"{folder_name} {' '.join(paths)} {compose_text}".lower()
    if "rtdetr" in text:
        return "RT-DETR"
    if "yolo" in text:
        return "YOLO"
    if "repvit" in text:
        return "RepVIT"
    if "mobilenet" in text:
        return "MobileNetV4"
    if "qwen" in text:
        return "Qwen"
    return ""


def _infer_import_endpoint(paths: list[str], readme_text: str) -> str:
    text = f"{' '.join(paths)} {readme_text}".lower()
    if "/api/v1/local-inference" in text:
        return "/api/v1/local-inference"
    if "/detect/image" in text:
        return "/detect/image"
    if "/infer" in text:
        return "/infer"
    if "/predict" in text:
        return "/predict"
    return ""


async def _read_import_manifest(files: list[UploadFile]) -> dict:
    entries: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    roots: set[str] = set()
    total_size = 0

    for file in files:
        relative = _safe_relative_path(file.filename or "")
        content = await file.read()
        await file.seek(0)
        size = len(content)
        total_size += size
        root = relative.split("/", 1)[0]
        roots.add(root)
        entries.append({"path": relative, "size": size})
        if relative.lower().endswith(("docker-compose.yml", "readme.md")):
            texts[relative] = content.decode("utf-8", errors="ignore")

    root = sorted(roots)[0] if roots else ""
    paths = [_strip_root(item["path"], root) for item in entries]
    compose_path = next((path for path in paths if path == "docker-compose.yml"), "")
    readme_path = next((path for path in paths if path.lower() == "readme.md"), "")
    compose_text = texts.get(f"{root}/{compose_path}" if root and compose_path else compose_path, "")
    readme_text = texts.get(f"{root}/{readme_path}" if root and readme_path else readme_path, "")
    weights = [path for path in paths if re.search(r"\.(pt|onnx|engine|safetensors|bin)$", path, re.I)]
    host_port, container_port = _extract_compose_port(compose_text)
    capability = _infer_import_capability(root, paths, compose_text, readme_text)
    compose_environment = _extract_compose_environment(compose_text)
    network_name = _extract_compose_network_name(compose_text)
    health_check_url = _infer_health_check(paths, readme_text)

    errors: list[str] = []
    warnings: list[str] = []
    if not files:
        errors.append("未选择模型目录")
    if len(roots) != 1:
        errors.append("导入内容必须只包含一个模型根目录")
    if "Dockerfile" not in paths:
        errors.append("缺少 Dockerfile")
    if not compose_text:
        errors.append("缺少 docker-compose.yml")
    if "app/main.py" not in paths:
        errors.append("缺少 app/main.py 服务入口")
    if compose_text and not _extract_service_name(compose_text):
        errors.append("docker-compose.yml 无法解析服务名")
    if compose_text and host_port is None:
        errors.append("docker-compose.yml 无法解析端口映射")
    if capability != "视觉语言模型" and not weights:
        errors.append("视觉模型目录缺少权重文件")
    if any(path.startswith("/") or "../" in path for path in paths):
        errors.append("目录中包含越级或绝对路径")
    if any("__pycache__" in path or path.startswith(".git/") or "/.git/" in path or "node_modules" in path for path in paths):
        warnings.append("目录中包含缓存、源码管理或依赖目录，建议清理后导入")
    if "requirements.txt" not in paths:
        warnings.append("缺少 requirements.txt")
    if not readme_text:
        warnings.append("缺少 README.md")

    description = ""
    for line in readme_text.splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            description = text[:512]
            break

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "detected": {
            "folder_name": root,
            "name": root or _extract_service_name(compose_text),
            "service_name": _extract_service_name(compose_text),
            "image_name": _extract_compose_value(compose_text, "image"),
            "container_name": _extract_compose_value(compose_text, "container_name"),
            "host_port": host_port,
            "container_port": container_port,
            "model_type": capability,
            "capability": capability,
            "framework": "vLLM Proxy / FastAPI" if capability == "视觉语言模型" else "PyTorch / FastAPI",
            "architecture": _infer_import_architecture(root, paths, compose_text),
            "weights": weights,
            "endpoint": _infer_import_endpoint(paths, readme_text),
            "health_check_url": health_check_url,
            "environment": compose_environment,
            "network_name": network_name,
            "model_size": _format_size(total_size),
            "description": description,
        },
        "files": {
            "count": len(entries),
            "total_size": total_size,
        },
    }


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "null":
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _as_list(value: Any) -> list:
    value = _parse_jsonish(value)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _infer_capability(model: dict) -> str:
    text = " ".join(
        str(model.get(key) or "")
        for key in ("name", "description", "model_type", "framework", "architecture")
    ).lower()
    if "vlm" in text or "视觉语言" in text or "多模态" in text:
        return "视觉语言模型"
    if "llm" in text or "语言模型" in text or "报告" in text:
        return "文本推理"
    if "classification" in text or "分类" in text:
        return "图像分类"
    if "detect" in text or "检测" in text or "yolo" in text:
        return "目标检测"
    return "智能推理"


def _health_state(status: str, container_status: Optional[str] = None) -> str:
    if status == "running" and (container_status in (None, "running")):
        return "healthy"
    if status in ("building", "starting", "stopping"):
        return "checking"
    if status == "error":
        return "error"
    return "unavailable"


def _public_endpoint(binding: Optional[dict], inference_url: Optional[str]) -> Optional[str]:
    if inference_url:
        return inference_url
    if not binding:
        return None
    host = binding.get("host_ip")
    port = binding.get("host_port")
    path = binding.get("inference_path") or ""
    if host and port:
        return f"http://{host}:{port}{path}"
    return None


def _status_response(model_id: int, data: Optional[dict]) -> dict:
    data = data or {}
    runtime_status = data.get("runtime_status") or data.get("runtimeStatus") or "unknown"
    container_status = data.get("container_status") or data.get("containerStatus")
    health_state = _health_state(runtime_status, container_status)
    inference_url = data.get("inference_url") or data.get("inferenceUrl")
    return {
        "model_id": model_id,
        "runtime_status": runtime_status,
        "status_label": STATUS_LABELS.get(runtime_status, runtime_status),
        "status_level": STATUS_LEVELS.get(runtime_status, "info"),
        "container_status": container_status,
        "health_state": health_state,
        "healthy": health_state == "healthy",
        "inference_url": inference_url,
        "endpoint": inference_url,
        "resources": data.get("resources"),
    }


def _normalize_model(
    model: dict,
    *,
    detail: Optional[dict] = None,
    io_schema: Optional[dict] = None,
    status: Optional[dict] = None,
) -> dict:
    source = {**model, **(detail or {})}
    binding = source.get("binding") or {}
    runtime_status = (status or {}).get("runtime_status") or source.get("runtime_status") or "stopped"
    container_status = (status or {}).get("container_status")
    inputs = _as_list((io_schema or {}).get("inputs"))
    outputs = _as_list((io_schema or {}).get("outputs"))
    endpoint = _public_endpoint(binding, source.get("inference_url") or (status or {}).get("inference_url"))
    tags = _as_list(source.get("tags"))

    return {
        "id": source.get("id"),
        "name": source.get("name"),
        "description": source.get("description") or "暂无说明",
        "capability": _infer_capability(source),
        "model_type": source.get("model_type"),
        "framework": source.get("framework"),
        "architecture": source.get("architecture"),
        "model_size": source.get("model_size"),
        "tags": tags,
        "runtime_status": runtime_status,
        "status_label": STATUS_LABELS.get(runtime_status, runtime_status),
        "status_level": STATUS_LEVELS.get(runtime_status, "info"),
        "health_state": _health_state(runtime_status, container_status),
        "container_status": container_status,
        "endpoint": endpoint,
        "has_binding": bool(binding),
        "image_name": binding.get("image_name"),
        "container_name": binding.get("container_name"),
        "health_check_path": binding.get("health_check_url"),
        "input_count": len(inputs),
        "output_count": len(outputs),
        "inputs": inputs,
        "outputs": outputs,
        "updated_at": source.get("update_time"),
        "created_at": source.get("create_time"),
    }


async def _load_model_detail(model: dict) -> dict:
    model_id = int(model["id"])
    detail_result, schema_result = await asyncio.gather(
        dam_model_library_client.get_model(model_id),
        dam_model_library_client.get_io_schema(model_id),
        return_exceptions=True,
    )
    detail = detail_result if isinstance(detail_result, dict) else None
    io_schema = schema_result if isinstance(schema_result, dict) else None
    return _normalize_model(model, detail=detail, io_schema=io_schema)


async def _run_import_lifecycle(
    *,
    model_id: int,
    target_dir: str,
    image_name: str,
    host_port: Optional[int],
    container_port: int,
    inference_path: str,
    health_check_url: Optional[str],
    network_name: str,
    environment: Optional[dict[str, str]],
) -> None:
    binding = None
    try:
        logger.info("导入模型生命周期开始: model_id={}, stage=build", model_id)
        build = await dam_model_library_client.build_image(
            context_path=target_dir,
            image_name=image_name,
        )
        logger.info("导入模型镜像构建完成: model_id={}, image={}", model_id, image_name)
        binding = await dam_model_library_client.bind_image(
            model_id,
            {
                "image_name": image_name,
                "host_port": host_port,
                "container_port": container_port,
                "inference_path": inference_path,
                "health_check_url": health_check_url or None,
                "extra_env": environment or None,
                "container_config": {
                    "network_mode": network_name or "bridge",
                    "restart_policy": {"Name": "unless-stopped"},
                },
                "remark": f"imported from {target_dir}",
            },
        )
        logger.info("导入模型绑定完成: model_id={}, stage=create-container", model_id)
        start = await dam_model_library_client.start_model(model_id)
        logger.info("导入模型启动验证完成: model_id={}, stage=stop", model_id)
        stop = await dam_model_library_client.stop_model(model_id)
        logger.info(
            "导入模型后台构建与启停验证完成: model_id={}, image={}, build={}, binding={}, start={}, stop={}",
            model_id,
            image_name,
            build.get("short_id") or build.get("image_id"),
            binding.get("id") or binding.get("model_id"),
            start.get("runtime_status"),
            stop.get("runtime_status"),
        )
    except Exception as exc:
        if binding:
            try:
                await dam_model_library_client.stop_model(model_id)
                logger.info("导入模型失败后已清理运行容器: model_id={}", model_id)
            except Exception as cleanup_exc:
                logger.warning("导入模型失败后清理容器失败: model_id={}, error={}", model_id, cleanup_exc)
        try:
            await dam_model_library_client.update_model(model_id, {"runtime_status": "error"})
        except Exception as status_exc:
            logger.warning("导入模型失败后更新状态失败: model_id={}, error={}", model_id, status_exc)
        logger.exception("导入模型后台构建或启停验证失败: model_id={}, image={}, error={}", model_id, image_name, exc)


@router.post("/import/validate")
async def validate_model_import(
    files: list[UploadFile] = File(default=[]),
    metadata: str = Form(default="{}"),
):
    """Validate an uploaded model service directory before registration."""
    try:
        result = await _read_import_manifest(files)
        form_metadata = _parse_jsonish(metadata) or {}
        if isinstance(form_metadata, dict):
            detected = result["detected"]
            for key in ("name", "capability", "framework", "architecture", "image_name", "container_name", "host_port", "endpoint"):
                value = form_metadata.get(key)
                if value not in (None, ""):
                    detected[key] = value
            if form_metadata.get("capability"):
                detected["model_type"] = form_metadata["capability"]
        return {"code": 200, "data": result}
    except ValueError as exc:
        return {
            "code": 200,
            "data": {
                "valid": False,
                "errors": [str(exc)],
                "warnings": [],
                "detected": {},
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型目录校验失败: {exc}") from exc


@router.post("/import/register")
async def register_model_import(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(default=[]),
    metadata: str = Form(default="{}"),
):
    """Register an uploaded model service directory after validation."""
    try:
        validation = await _read_import_manifest(files)
        if not validation["valid"]:
            return {
                "code": 200,
                "message": "模型目录校验未通过",
                "data": validation,
            }

        form_metadata = _parse_jsonish(metadata) or {}
        if not isinstance(form_metadata, dict):
            form_metadata = {}

        detected = validation["detected"]
        folder_name = str(form_metadata.get("folder_name") or detected.get("folder_name") or detected.get("name") or "").strip()
        if not folder_name:
            raise HTTPException(status_code=400, detail="无法识别模型目录名称")
        if not re.match(r"^[\w.-]+$", folder_name):
            raise HTTPException(status_code=400, detail="模型目录名称只能包含字母、数字、下划线、点和短横线")

        target_dir = IMPORT_ROOT / folder_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            relative = _safe_relative_path(file.filename or "")
            path = PurePosixPath(relative)
            stripped = _strip_root(str(path), folder_name)
            target_file = target_dir / stripped
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with target_file.open("wb") as output:
                shutil.copyfileobj(file.file, output)
        _restore_import_ownership(target_dir)

        tags = form_metadata.get("tags") if isinstance(form_metadata.get("tags"), list) else []
        tags.append("imported")
        tags.append(f"folder:{folder_name}")

        payload = {
            "name": str(form_metadata.get("name") or detected.get("name") or folder_name),
            "description": str(form_metadata.get("description") or detected.get("description") or "导入的模型服务目录")[:512],
            "tags": tags,
            "framework": form_metadata.get("framework") or detected.get("framework"),
            "architecture": form_metadata.get("architecture") or detected.get("architecture"),
            "model_type": form_metadata.get("capability") or detected.get("model_type"),
            "model_size": detected.get("model_size"),
            "runtime_status": "building",
        }
        image_name = str(form_metadata.get("image_name") or detected.get("image_name") or _default_import_image_name(folder_name)).strip()
        host_port = _coerce_int(form_metadata.get("host_port")) or _coerce_int(detected.get("host_port"))
        container_port = _coerce_int(form_metadata.get("container_port")) or _coerce_int(detected.get("container_port")) or host_port
        if not container_port:
            raise HTTPException(status_code=400, detail="无法识别容器服务端口")
        inference_path = str(form_metadata.get("endpoint") or detected.get("endpoint") or "/infer").strip()

        model = await dam_model_library_client.create_model(payload)
        model_id = int(model["id"])
        background_tasks.add_task(
            _run_import_lifecycle,
            model_id=model_id,
            target_dir=str(target_dir),
            image_name=image_name,
            host_port=host_port,
            container_port=container_port,
            inference_path=inference_path,
            health_check_url=detected.get("health_check_url"),
            network_name=str(detected.get("network_name") or "bridge"),
            environment=detected.get("environment") if isinstance(detected.get("environment"), dict) else None,
        )
        return {
            "code": 200,
            "message": "模型注册成功，已提交后台镜像构建和一次启停验证",
            "data": {
                **model,
                "import_path": str(target_dir),
                "image_name": image_name,
                "runtime_status": "building",
                "lifecycle": {"status": "submitted"},
            },
        }
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型注册失败: {exc}") from exc


@router.get("/models")
async def list_models(
    keyword: Optional[str] = Query(None),
    runtime_status: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    """List model-library records as a compact user-facing catalog."""
    try:
        result = await dam_model_library_client.list_models(
            keyword=keyword,
            runtime_status=runtime_status,
            framework=framework,
            page_num=page_num,
            page_size=page_size,
        )
        rows = result.get("data") or []
        # Keep the catalog fast: details/IO schema are loaded only when a user opens a model.
        records = [_normalize_model(row) for row in rows]
        return {
            "code": 200,
            "data": {
                "records": records,
                "total": result.get("total", len(records)),
                "page_num": result.get("page_num", page_num),
                "page_size": result.get("page_size", page_size),
            },
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取模型库失败: {exc}") from exc


@router.get("/models/{model_id}")
async def get_model(model_id: int):
    """Get model detail for display."""
    try:
        detail, io_schema, status = await asyncio.gather(
            dam_model_library_client.get_model(model_id),
            dam_model_library_client.get_io_schema(model_id),
            dam_model_library_client.get_status(model_id),
            return_exceptions=True,
        )
        if isinstance(detail, Exception):
            raise detail
        return {
            "code": 200,
            "data": _normalize_model(
                detail,
                detail=detail if isinstance(detail, dict) else None,
                io_schema=io_schema if isinstance(io_schema, dict) else None,
                status=status if isinstance(status, dict) else None,
            ),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取模型详情失败: {exc}") from exc


@router.put("/models/{model_id}")
async def update_model(model_id: int, payload: dict[str, Any] = Body(default={})):
    """Update editable model metadata."""
    try:
        update_payload: dict[str, Any] = {}
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="模型名称不能为空")
            update_payload["name"] = name[:128]
        if "description" in payload:
            update_payload["description"] = str(payload.get("description") or "")[:512]
        if "tags" in payload:
            tags = payload.get("tags")
            if not isinstance(tags, list):
                raise HTTPException(status_code=400, detail="模型标签必须是数组")
            update_payload["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
        if not update_payload:
            raise HTTPException(status_code=400, detail="没有可更新的模型信息")

        result = await dam_model_library_client.update_model(model_id, update_payload)
        return {
            "code": 200,
            "message": "模型信息已更新",
            "data": _normalize_model(result),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型更新失败: {exc}") from exc


@router.delete("/models/{model_id}")
async def delete_model(model_id: int):
    """Delete a stopped model registry record."""
    try:
        await dam_model_library_client.delete_model(model_id)
        return {"code": 200, "message": "模型已删除", "data": {"id": model_id}}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型删除失败: {exc}") from exc


@router.post("/models/{model_id}/health-check")
async def health_check_model(model_id: int):
    """Check whether a model looks usable from the model-library runtime state."""
    try:
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, status),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型健康测试失败: {exc}") from exc


@router.post("/models/{model_id}/start")
async def start_model(model_id: int):
    """Start a model through the model-library lifecycle service."""
    try:
        result = await dam_model_library_client.start_model(model_id)
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, {**result, **status}),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型启动失败: {exc}") from exc


@router.post("/models/{model_id}/stop")
async def stop_model(model_id: int, timeout: int = Query(30, ge=1, le=300)):
    """Stop a model through the model-library lifecycle service."""
    try:
        result = await dam_model_library_client.stop_model(model_id, timeout_seconds=timeout)
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, {**result, **status}),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型停止失败: {exc}") from exc
