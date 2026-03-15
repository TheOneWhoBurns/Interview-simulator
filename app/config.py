from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Interview Simulator"
    data_dir: Path = Path("data")
    jobs_dir: Path = Path("data/jobs")
    default_model: str = "sonnet"
    eval_model: str = "sonnet"
    code_timeout: int = 10
    code_memory_mb: int = 128
    tts_voice: str = "Daniel"
    host: str = "127.0.0.1"
    port: int = 8000

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
