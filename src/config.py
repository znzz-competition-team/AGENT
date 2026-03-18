from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # AI Provider Settings (支持多模型)
    ai_provider: str = "deepseek"  # openai, deepseek, zhipu, moonshot, etc.
    ai_api_key: Optional[str] = None
    ai_model: str = "deepseek-chat"
    ai_base_url: Optional[str] = None  # 自定义 API 基础 URL
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2000
    
    # 兼容旧版 OpenAI 配置
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000
    
    # DeepSeek 配置
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    
    # 智谱 AI 配置
    zhipu_api_key: Optional[str] = None
    zhipu_model: str = "glm-4"
    
    # Moonshot (月之暗面) 配置
    moonshot_api_key: Optional[str] = None
    moonshot_model: str = "moonshot-v1-8k"
    
    # CrewAI Settings
    crewai_max_iterations: int = 15
    crewai_max_exec_time: int = 300
    crewai_verbose: bool = True
    
    # Database Settings
    database_url: str = "sqlite:///./student_profiler_new.db"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True
    
    # Processing Settings
    video_frame_rate: int = 1
    audio_sample_rate: int = 16000
    max_file_size_mb: int = 500
    
    # Output Settings
    output_dir: str = "data/output"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()

# 预定义的模型配置
AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-3.5-turbo"
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "default_model": "deepseek-chat"
    },
    "zhipu": {
        "name": "智谱 AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-plus", "glm-4-flash", "glm-4v"],
        "default_model": "glm-4"
    },
    "moonshot": {
        "name": "Moonshot (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-8k"
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "default_model": "qwen-turbo"
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "models": [],
        "default_model": ""
    }
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
    """获取当前 AI 配置"""
    # 尝试从环境变量中读取配置
    import os
    from dotenv import load_dotenv
    
    # 加载 .env 文件
    load_dotenv()
    
    # 首先尝试读取环境变量中的配置
    provider = os.getenv("AI_PROVIDER", settings.ai_provider)
    api_key = os.getenv("AI_API_KEY", settings.ai_api_key)
    model = os.getenv("AI_MODEL", settings.ai_model)
    base_url = os.getenv("AI_BASE_URL", settings.ai_base_url)
    temperature = float(os.getenv("AI_TEMPERATURE", str(settings.ai_temperature)))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", str(settings.ai_max_tokens)))
    
    # 根据提供商获取配置
    if provider == "openai":
        return {
            "api_key": api_key or settings.openai_api_key,
            "model": model or settings.openai_model,
            "base_url": base_url or AI_PROVIDERS["openai"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    elif provider == "deepseek":
        return {
            "api_key": api_key or settings.deepseek_api_key,
            "model": model or settings.deepseek_model,
            "base_url": base_url or AI_PROVIDERS["deepseek"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    elif provider == "zhipu":
        return {
            "api_key": api_key or settings.zhipu_api_key,
            "model": model or settings.zhipu_model,
            "base_url": base_url or AI_PROVIDERS["zhipu"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    elif provider == "moonshot":
        return {
            "api_key": api_key or settings.moonshot_api_key,
            "model": model or settings.moonshot_model,
            "base_url": base_url or AI_PROVIDERS["moonshot"]["base_url"],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    else:  # custom
        return {
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
