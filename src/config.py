from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AI provider settings
    ai_provider: str = "qwen"
    ai_api_key: Optional[str] = "sk-8ac33a82e02b42429a5b30b3ced6dfe3"
    ai_model: str = "qwen3.6-plus"
    ai_base_url: Optional[str] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2000

    # OpenAI-compatible legacy settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000

    # Other providers
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    zhipu_api_key: Optional[str] = None
    zhipu_model: str = "glm-4"
    moonshot_api_key: Optional[str] = None
    moonshot_model: str = "moonshot-v1-8k"

    # CrewAI
    crewai_max_iterations: int = 15
    crewai_max_exec_time: int = 300
    crewai_verbose: bool = True

    # Database
    database_url: str = "sqlite:///./student_profiler_new.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True

    # Processing
    video_frame_rate: int = 1
    audio_sample_rate: int = 16000
    max_file_size_mb: int = 500

    # Output
    output_dir: str = "data/output"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-3.5-turbo",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    "zhipu": {
        "name": "Zhipu AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-plus", "glm-4-flash", "glm-4v"],
        "default_model": "glm-4",
    },
    "moonshot": {
        "name": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-8k",
    },
    "qwen": {
        "name": "Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen3.6-plus", "qwen3.5-plus", "qwen3-vl-plus", "qwen3-vl-flash",
            "qwen-vl-ocr-latest", "qwen-turbo", "qwen-plus", "qwen-max", "qvq-max",
        ],
        "default_model": "qwen3.6-plus",
    },
    "custom": {
        "name": "Custom",
        "base_url": "",
        "models": [],
        "default_model": "",
    },
}


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    return get_project_root() / "data"


def get_input_dir() -> Path:
    return get_data_dir() / "input"


def get_output_dir() -> Path:
    return Path(settings.output_dir)


def get_ai_config():
    """Get effective AI configuration from env + defaults."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    provider = os.getenv("AI_PROVIDER", settings.ai_provider)
    api_key = os.getenv("AI_API_KEY", settings.ai_api_key)
    model = os.getenv("AI_MODEL", settings.ai_model)
    base_url = os.getenv("AI_BASE_URL", settings.ai_base_url)
    temperature = float(os.getenv("AI_TEMPERATURE", str(settings.ai_temperature)))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", str(settings.ai_max_tokens)))

    if provider == "openai":
        return {
            "api_key": api_key or settings.openai_api_key,
            "model": model or settings.openai_model,
            "base_url": base_url or AI_PROVIDERS["openai"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    if provider == "deepseek":
        return {
            "api_key": api_key or settings.deepseek_api_key,
            "model": model or settings.deepseek_model,
            "base_url": base_url or AI_PROVIDERS["deepseek"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    if provider == "zhipu":
        return {
            "api_key": api_key or settings.zhipu_api_key,
            "model": model or settings.zhipu_model,
            "base_url": base_url or AI_PROVIDERS["zhipu"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    if provider == "moonshot":
        return {
            "api_key": api_key or settings.moonshot_api_key,
            "model": model or settings.moonshot_model,
            "base_url": base_url or AI_PROVIDERS["moonshot"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    if provider == "qwen":
        return {
            "api_key": api_key or settings.ai_api_key,
            "model": model or AI_PROVIDERS["qwen"]["default_model"],
            "base_url": base_url or AI_PROVIDERS["qwen"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
