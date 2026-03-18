import speech_recognition as sr
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from pydub import AudioSegment
from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class AudioProcessor(BaseProcessor):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.sample_rate = self.config.get("sample_rate", 16000)
        self.recognizer = sr.Recognizer()
        
    def process(self, file_path: str) -> Dict[str, Any]:
        try:
            self.validate_file(file_path)
            file_info = self.get_file_info(file_path)
            
            audio_data = self.load_audio(file_path)
            audio_features = self.extract_audio_features(audio_data)
            transcription = self.transcribe_audio(file_path)
            segments = self.segment_audio(audio_data)
            
            result = {
                "file_info": file_info,
                "audio_info": {
                    "duration": len(audio_data) / 1000.0,
                    "sample_rate": audio_data.frame_rate,
                    "channels": audio_data.channels,
                    "frame_width": audio_data.frame_width
                },
                "audio_features": audio_features,
                "transcription": transcription,
                "segments": segments,
                "status": "success"
            }
            
            self.logger.info(f"Audio processing completed: {file_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing audio {file_path}: {str(e)}")
            return {
                "file_path": file_path,
                "status": "error",
                "error_message": str(e)
            }
    
    def load_audio(self, file_path: str) -> AudioSegment:
        try:
            audio = AudioSegment.from_file(file_path)
            audio = audio.set_frame_rate(self.sample_rate)
            return audio
        except Exception as e:
            raise ValueError(f"Failed to load audio file: {str(e)}")
    
    def extract_audio_features(self, audio: AudioSegment) -> Dict[str, Any]:
        samples = np.array(audio.get_array_of_samples())
        
        if len(samples.shape) > 1:
            samples = np.mean(samples, axis=1)
        
        features = {
            "duration_seconds": len(audio) / 1000.0,
            "max_amplitude": float(np.max(np.abs(samples))),
            "mean_amplitude": float(np.mean(np.abs(samples))),
            "rms": float(np.sqrt(np.mean(samples ** 2))),
            "zero_crossing_rate": float(np.mean(np.diff(np.sign(samples)) != 0)),
            "energy": float(np.sum(samples ** 2))
        }
        
        if len(samples) > 0:
            features["std_amplitude"] = float(np.std(samples))
            features["min_amplitude"] = float(np.min(samples))
        
        return features
    
    def transcribe_audio(self, file_path: str, language: str = "zh-CN") -> Dict[str, Any]:
        try:
            with sr.AudioFile(file_path) as source:
                audio_data = self.recognizer.record(source)
                
            try:
                text = self.recognizer.recognize_google(audio_data, language=language)
                return {
                    "text": text,
                    "language": language,
                    "confidence": 0.8,
                    "method": "google_speech"
                }
            except sr.UnknownValueError:
                return {
                    "text": "",
                    "language": language,
                    "confidence": 0.0,
                    "method": "google_speech",
                    "error": "Speech could not be understood"
                }
            except sr.RequestError as e:
                self.logger.warning(f"Speech recognition service error: {e}")
                return {
                    "text": "",
                    "language": language,
                    "confidence": 0.0,
                    "method": "google_speech",
                    "error": str(e)
                }
                
        except Exception as e:
            self.logger.error(f"Transcription error: {str(e)}")
            return {
                "text": "",
                "language": language,
                "confidence": 0.0,
                "method": "google_speech",
                "error": str(e)
            }
    
    def segment_audio(self, audio: AudioSegment, segment_length: int = 30) -> List[Dict[str, Any]]:
        segments = []
        duration_ms = len(audio)
        segment_length_ms = segment_length * 1000
        
        for i in range(0, duration_ms, segment_length_ms):
            end_time = min(i + segment_length_ms, duration_ms)
            segment = audio[i:end_time]
            
            segment_info = {
                "segment_index": len(segments),
                "start_time": i / 1000.0,
                "end_time": end_time / 1000.0,
                "duration": (end_time - i) / 1000.0
            }
            segments.append(segment_info)
        
        return segments
    
    def convert_to_wav(self, file_path: str, output_path: str) -> str:
        try:
            audio = AudioSegment.from_file(file_path)
            audio = audio.set_frame_rate(self.sample_rate)
            audio = audio.set_channels(1)
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            audio.export(output_path, format="wav")
            self.logger.info(f"Audio converted to WAV: {output_path}")
            return output_path
            
        except Exception as e:
            raise ValueError(f"Failed to convert audio to WAV: {str(e)}")
    
    def validate_file(self, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        valid_extensions = {'.wav', '.mp3', '.flac', '.aac', '.m4a', '.ogg'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Invalid audio format: {path.suffix}")
        
        return True