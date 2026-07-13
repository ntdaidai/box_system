"""通用响应模型"""

from pydantic import BaseModel
from typing import Any, Optional, List, Generic, TypeVar

T = TypeVar("T")


class Result(BaseModel):
    """统一响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PageResult(BaseModel):
    """分页响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None
    total: int = 0
    page_num: int = 1
    page_size: int = 10

    @classmethod
    def from_page(cls, records: list, total: int, page_num: int, page_size: int) -> "PageResult":
        return cls(
            code=200,
            message="success",
            data=records,
            total=total,
            page_num=page_num,
            page_size=page_size,
        )
