"""Bộ tổng hợp sự kiện cho việc phát hiện trong cửa sổ 5 giây."""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np

from src.domain.entities import Detection, VisionEvent


logger = logging.getLogger(__name__)


class PresenceState(Enum):
    """Các trạng thái của máy trạng thái cho việc phát hiện sự hiện diện của người."""
    IDLE = "idle"
    PERSON_PRESENT = "person_present"


class EventAggregator:
    """
    Tổng hợp các phát hiện người qua các cửa sổ thời gian.
    
    Máy trạng thái (State machine):
    - IDLE: Không phát hiện người trong vùng
    - PERSON_PRESENT: Phát hiện người, đang tích lũy thống kê
    
    Các sự kiện được phát ra:
    - person_present_start: Phát hiện đầu tiên sau trạng thái IDLE
    - person_still_present: Heartbeat mỗi window_sec khi người vẫn còn
    - person_left: Không phát hiện trong gap_sec sau khi đã hiện diện
    """
    
    def __init__(
        self,
        camera_id: str,
        window_sec: int = 5,
        gap_sec: int = 2
    ):
        """
        Khởi tạo bộ tổng hợp sự kiện.
        
        Args:
            camera_id: Định danh camera cho các sự kiện
            window_sec: Thời lượng cửa sổ cho các sự kiện heartbeat (giây)
            gap_sec: Thời lượng khoảng trống để kích hoạt sự kiện person_left (giây)
        """
        self.camera_id = camera_id
        self.window_sec = window_sec
        self.gap_sec = gap_sec
        
        # Trạng thái
        self._state = PresenceState.IDLE
        self._window_start: Optional[datetime] = None
        self._last_detection_time: Optional[datetime] = None
        self._session_start: Optional[datetime] = None
        
        # Thống kê tích lũy cho cửa sổ hiện tại
        self._person_counts: list[int] = []
        self._confidences: list[float] = []
        self._last_frame: Optional[np.ndarray] = None
        self._is_first_window = True
    
    @property
    def state(self) -> PresenceState:
        """Trạng thái hiện diện hiện tại."""
        return self._state
    
    def update(
        self,
        detections: list[Detection],
        frame: np.ndarray,
        current_time: Optional[datetime] = None
    ) -> Optional[VisionEvent]:
        """
        Cập nhật bộ tổng hợp với các phát hiện mới.
        
        Args:
            detections: Danh sách các phát hiện từ khung hình hiện tại
            frame: Khung hình hiện tại (để chụp ảnh snapshot)
            current_time: Thời gian hiện tại (mặc định: now)
        
        Returns:
            VisionEvent nếu một sự kiện cần được phát ra, ngược lại là None
        """
        now = current_time or datetime.now(timezone.utc)
        
        # Lọc chỉ các phát hiện bên trong vùng
        inside_zone = [d for d in detections if d.is_inside_zone]
        has_person = len(inside_zone) > 0
        
        event: Optional[VisionEvent] = None
        
        if self._state == PresenceState.IDLE:
            if has_person:
                # Chuyển trạng thái: IDLE -> PERSON_PRESENT
                self._state = PresenceState.PERSON_PRESENT
                self._window_start = now
                self._session_start = now
                self._last_detection_time = now
                self._is_first_window = True
                
                # Bắt đầu tích lũy
                self._person_counts = [len(inside_zone)]
                self._confidences = [d.confidence for d in inside_zone]
                self._last_frame = frame.copy()
                
                logger.debug(f"State: IDLE -> PERSON_PRESENT at {now}")
        
        elif self._state == PresenceState.PERSON_PRESENT:
            if has_person:
                # Tiếp tục tích lũy
                self._last_detection_time = now
                self._person_counts.append(len(inside_zone))
                self._confidences.extend([d.confidence for d in inside_zone])
                self._last_frame = frame.copy()
                
                # Kiểm tra xem cửa sổ đã hoàn tất chưa
                window_elapsed = (now - self._window_start).total_seconds()
                
                if window_elapsed >= self.window_sec:
                    # Phát sự kiện
                    event_type = "person_present_start" if self._is_first_window else "person_still_present"
                    event = self._create_event(now, event_type)
                    
                    # Đặt lại cửa sổ
                    self._window_start = now
                    self._person_counts = []
                    self._confidences = []
                    self._is_first_window = False
                    
                    logger.debug(f"Emitting {event_type} event")
            else:
                # Không phát hiện người - kiểm tra khoảng trống (gap)
                gap_elapsed = (now - self._last_detection_time).total_seconds()
                
                if gap_elapsed >= self.gap_sec:
                    # Chuyển trạng thái: PERSON_PRESENT -> IDLE
                    event = self._create_event(now, "person_left")
                    
                    # Đặt lại trạng thái
                    self._state = PresenceState.IDLE
                    self._window_start = None
                    self._session_start = None
                    self._last_detection_time = None
                    self._person_counts = []
                    self._confidences = []
                    self._last_frame = None
                    self._is_first_window = True
                    
                    logger.debug(f"State: PERSON_PRESENT -> IDLE (person left)")
        
        return event
    
    def _create_event(self, end_time: datetime, event_type: str) -> VisionEvent:
        """Tạo một VisionEvent từ các thống kê đã tích lũy."""
        avg_count = sum(self._person_counts) / len(self._person_counts) if self._person_counts else 0
        max_count = max(self._person_counts) if self._person_counts else 0
        avg_conf = sum(self._confidences) / len(self._confidences) if self._confidences else 0
        max_conf = max(self._confidences) if self._confidences else 0
        
        return VisionEvent.create(
            camera_id=self.camera_id,
            ts_start=self._window_start or end_time,
            ts_end=end_time,
            person_count=max_count,
            conf_avg=round(avg_conf, 3),
            conf_max=round(max_conf, 3),
            event_type=event_type,
            frame_uri=""  # Sẽ được điền bởi use case
        )
    
    def get_snapshot_frame(self) -> Optional[np.ndarray]:
        """Lấy khung hình cuối cùng đã chụp để làm snapshot."""
        return self._last_frame
    
    def force_end_session(self, current_time: Optional[datetime] = None) -> Optional[VisionEvent]:
        """
        Buộc kết thúc phiên hiện tại (ví dụ: khi tắt ứng dụng).
        
        Returns:
            VisionEvent nếu phiên đang hoạt động, ngược lại là None
        """
        if self._state != PresenceState.PERSON_PRESENT:
            return None
        
        now = current_time or datetime.now(timezone.utc)
        event = self._create_event(now, "person_left")
        
        # Đặt lại trạng thái
        self._state = PresenceState.IDLE
        self._window_start = None
        self._session_start = None
        self._last_detection_time = None
        self._person_counts = []
        self._confidences = []
        self._last_frame = None
        
        return event
