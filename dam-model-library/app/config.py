from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "dam_system"

    # Docker
    docker_host: str = "unix:///var/run/docker.sock"

    # 服务
    host: str = "0.0.0.0"
    port: int = 5001

    # 常驻模型：run 模式下不会在推理后停止这些模型。
    resident_model_ids: str = "10,13,14"
    workflow_local_llm_node_timeout: int = 240
    workflow_cloud_node_timeout: int = 30

    @property
    def resident_model_id_set(self) -> set[int]:
        values: set[int] = set()
        for item in str(self.resident_model_ids or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                values.add(int(item))
            except ValueError:
                continue
        return values

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    class Config:
        env_file = ".env"


settings = Settings()
