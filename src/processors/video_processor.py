import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging
from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class VideoProcessor(BaseProcessor):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.frame_rate = self.config.get("frame_rate", 1)
        
    def process(self, file_path: str) -> Dict[str, Any]:
        try:
            self.validate_file(file_path)
            file_info = self.get_file_info(file_path)
            
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {file_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            frames = self.extract_frames(cap, fps)
            audio_info = self.extract_audio_info(file_path)
            
            cap.release()
            
            result = {
                "file_info": file_info,
                "video_info": {
                    "fps": fps,
                    "frame_count": frame_count,
                    "duration": duration,
                    "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                },
                "frames": frames,
                "audio_info": audio_info,
                "status": "success"
            }
            
            self.logger.info(f"Video processing completed: {file_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing video {file_path}: {str(e)}")
            return {
                "file_path": file_path,
                "status": "error",
                "error_message": str(e)
            }
    
    def extract_frames(self, cap, fps: int, max_frames: int = 30) -> List[Dict[str, Any]]:
        frames = []
        frame_interval = int(fps / self.frame_rate) if fps > 0 else 1
        frame_idx = 0
        extracted_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret or extracted_count >= max_frames:
                break
                
            if frame_idx % frame_interval == 0:
                frame_data = {
                    "frame_number": frame_idx,
                    "timestamp": frame_idx / fps if fps > 0 else 0,
                    "shape": frame.shape,
                    "mean_color": np.mean(frame, axis=(0, 1)).tolist()
                }
                frames.append(frame_data)
                extracted_count += 1
            
            frame_idx += 1
        
        return frames
    
    def extract_audio_info(self, file_path: str) -> Dict[str, Any]:
        try:
            import moviepy.editor as mp
            video = mp.VideoFileClip(file_path)
            audio = video.audio
            
            if audio is None:
                return {"has_audio": False}
            
            duration = audio.duration
            audio_info = {
                "has_audio": True,
                "duration": duration,
                "sample_rate": 44100
            }
            
            video.close()
            return audio_info
            
        except Exception as e:
            self.logger.warning(f"Could not extract audio info: {str(e)}")
            return {"has_audio": False, "error": str(e)}
    
    def validate_file(self, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")
        
        valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Invalid video format: {path.suffix}")
        
        return True
    
    def extract_keyframes(self, file_path: str, output_dir: str, num_keyframes: int = 10) -> List[str]:
        output_path = self.ensure_output_dir(output_dir)
        keyframe_paths = []
        
        cap = cv2.VideoCapture(file_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        frame_indices = np.linspace(0, total_frames - 1, num_keyframes, dtype=int)
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if ret:
                output_file = output_path / f"keyframe_{i:03d}.jpg"
                cv2.imwrite(str(output_file), frame)
                keyframe_paths.append(str(output_file))
        
        cap.release()
        return keyframe_paths