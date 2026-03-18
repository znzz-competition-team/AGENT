from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logger
        
    @abstractmethod
    def process(self, file_path: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def validate_file(self, file_path: str) -> bool:
        pass
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return {
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "file_extension": path.suffix,
            "file_path": str(path.absolute())
        }
    
    def ensure_output_dir(self, output_dir: str) -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path