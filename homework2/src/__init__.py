# Vision Event Pipeline - Clean Architecture
# Entry point: python main.py

from src.presentation.main_loop import VisionApp
from src.infrastructure.config import load_config

__all__ = ["VisionApp", "load_config"]
