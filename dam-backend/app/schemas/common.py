"""通用请求/响应模型"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field


class PageQuery(BaseModel):
    """分页查询参数"""
    page_num: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数")


class Result(BaseModel):
    """统一响应体，与前端 request.js 的拦截器约定一致：code==200 视为成功"""
    code: int = 200
    data: Optional[Any] = None
    message: Optional[str] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "操作成功"):
        return cls(code=200, data=data, message=message)

    @classmethod
    def error(cls, message: str = "操作失败", code: int = 500):
        return cls(code=code, data=None, message=message)


class PageResult(BaseModel):
    """分页响应"""
    code: int = 200
    data: dict = Field(default_factory=lambda: {"records": [], "total": 0, "page_num": 1, "page_size": 10})
    message: Optional[str] = None

    @classmethod
    def from_page(cls, records: List[Any], total: int, page_num: int, page_size: int):
        return cls(code=200, data={
            "records": records,
            "total": total,
            "page_num": page_num,
            "page_size": page_size,
        })
