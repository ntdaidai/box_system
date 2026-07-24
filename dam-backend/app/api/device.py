"""设备管理接口"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.core.security import require_auth
from app.core.cache import cached, invalidate_cache
from app.models.device import Device
from app.models.user import User
from app.schemas.common import Result, PageResult, PageQuery
from app.schemas.device import DeviceCreateRequest, DeviceUpdateRequest

router = APIRouter()


def _device_to_dict(d: Device) -> dict:
    return {
        "id": d.id,
        "device_code": d.device_code,
        "device_name": d.device_name,
        "device_type": d.device_type,
        "serial_port": d.serial_port,
        "modbus_addr": d.modbus_addr,
        "location": d.location,
        "longitude": d.longitude,
        "latitude": d.latitude,
        "status": d.status,
        "create_time": d.create_time.isoformat() if d.create_time else None,
        "update_time": d.update_time.isoformat() if d.update_time else None,
    }


@router.get("/list", response_model=PageResult)
@cached(ttl=300, prefix="device:list")
async def list_devices(
    query: PageQuery = Depends(),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取设备列表（分页）"""
    # 过滤逻辑删除的记录
    total = db.query(Device).filter(Device.deleted == 0).count()
    records = (
        db.query(Device)
        .filter(Device.deleted == 0)
        .order_by(Device.id.desc())
        .offset((query.page_num - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return PageResult.from_page(
        records=[_device_to_dict(d) for d in records],
        total=total,
        page_num=query.page_num,
        page_size=query.page_size,
    )


@router.get("/all", response_model=Result)
@cached(ttl=300, prefix="device:all")
async def list_all_devices(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取所有设备（不分页）"""
    devices = db.query(Device).filter(Device.deleted == 0).all()
    return Result.success([_device_to_dict(d) for d in devices])


@router.get("/{device_id}", response_model=Result)
@cached(ttl=600, prefix="device:detail")
async def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取设备详情"""
    device = db.query(Device).filter(Device.id == device_id, Device.deleted == 0).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return Result.success(_device_to_dict(device))


@router.get("/{device_id}/status", response_model=Result)
def get_device_status(
    device_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取设备在线状态"""
    device = db.query(Device).filter(Device.id == device_id, Device.deleted == 0).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return Result.success({
        "device_id": device.id,
        "device_code": device.device_code,
        "status": "online" if device.status == 1 else "offline",
    })


@router.post("", response_model=Result)
async def create_device(
    req: DeviceCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """添加设备"""
    existing = db.query(Device).filter(Device.device_code == req.device_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备编号已存在")

    device = Device(**req.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    logger.info(f"设备已创建: {device.device_code}")

    # 清除设备列表缓存
    await invalidate_cache("device:*")

    return Result.success(_device_to_dict(device), "设备添加成功")


@router.put("/{device_id}", response_model=Result)
async def update_device(
    device_id: int,
    req: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """更新设备信息"""
    device = db.query(Device).filter(Device.id == device_id, Device.deleted == 0).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    db.commit()
    logger.info(f"设备已更新: {device.device_code}")

    # 清除设备相关缓存
    await invalidate_cache("device:*")

    return Result.success(_device_to_dict(device), "设备更新成功")


@router.delete("/{device_id}", response_model=Result)
async def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """删除设备（逻辑删除）"""
    device = db.query(Device).filter(Device.id == device_id, Device.deleted == 0).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    device.deleted = 1
    db.commit()
    logger.info(f"设备已删除: {device.device_code}")

    # 清除设备相关缓存
    await invalidate_cache("device:*")

    return Result.success(None, "设备已删除")
