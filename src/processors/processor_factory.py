from typing import Dict, Any, Optional
from pathlib import Path
import logging
from .base_processor import BaseProcessor
from .video_processor import VideoProcessor
from .audio_processor import AudioProcessor
from .document_processor import DocumentProcessor
from .ppt_processor import PPTProcessor

logger = logging.getLogger(__name__)

class ProcessorFactory:
    _processors: Dict[str, BaseProcessor] = {}
    
    @classmethod
    def get_processor(cls, media_type: str, config: Optional[Dict[str, Any]] = None) -> BaseProcessor:
        processor_key = f"{media_type}_{id(config) if config else 'default'}"
        
        if processor_key not in cls._processors:
            if media_type == "video":
                cls._processors[processor_key] = VideoProcessor(config)
            elif media_type == "audio":
                cls._processors[processor_key] = AudioProcessor(config)
            elif media_type == "document":
                cls._processors[processor_key] = DocumentProcessor(config)
            elif media_type == "ppt":
                cls._processors[processor_key] = PPTProcessor()
            else:
                raise ValueError(f"Unsupported media type: {media_type}")
        
        return cls._processors[processor_key]
    
    @classmethod
    def detect_media_type(cls, file_path: str) -> str:
        path = Path(file_path)
        extension = path.suffix.lower()
        
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        audio_extensions = {'.wav', '.mp3', '.flac', '.aac', '.m4a', '.ogg'}
        document_extensions = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt'}
        ppt_extensions = {'.pptx', '.ppt'}
        
        if extension in video_extensions:
            return "video"
        elif extension in audio_extensions:
            return "audio"
        elif extension in document_extensions:
            return "document"
        elif extension in ppt_extensions:
            return "ppt"
        else:
            raise ValueError(f"Cannot detect media type for extension: {extension}")
    
    @classmethod
    def process_file(cls, file_path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            media_type = cls.detect_media_type(file_path)
            processor = cls.get_processor(media_type, config)
            result = processor.process(file_path)
            
            logger.info(f"Successfully processed {media_type} file: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {str(e)}")
            return {
                "file_path": file_path,
                "status": "error",
                "error_message": str(e)
            }
    
    @classmethod
    def batch_process(cls, file_paths: list, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        results = {
            "total_files": len(file_paths),
            "successful": 0,
            "failed": 0,
            "results": []
        }
        
        for file_path in file_paths:
            result = cls.process_file(file_path, config)
            results["results"].append(result)
            
            if result.get("status") == "success":
                results["successful"] += 1
            else:
                results["failed"] += 1
        
        return results