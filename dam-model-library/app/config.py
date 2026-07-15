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

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    class Config:
        env_file = ".env"


settings = Settings()
