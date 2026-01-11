"""Event aggregator for 5-second window detection aggregation."""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np

from src.domain.entities import Detection, VisionEvent


logger = logging.getLogger(__name__)


class PresenceState(Enum):
    """State machine states for person presence detection."""
    IDLE = "idle"
    PERSON_PRESENT = "person_present"


class EventAggregator:
    """
    Aggregates person detections over time windows.
    
    State machine:
    - IDLE: No person detected in zone
    - PERSON_PRESENT: Person detected, accumulating stats
    
    Events emitted:
    - person_present_start: First detection after IDLE
    - person_still_present: Heartbeat every window_sec while person present
    - person_left: No detection for gap_sec after being present
    """
    
    def __init__(
        self,
        camera_id: str,
        window_sec: int = 5,
        gap_sec: int = 2
    ):
        """
        Initialize event aggregator.
        
        Args:
            camera_id: Camera identifier for events
            window_sec: Window duration for heartbeat events (seconds)
            gap_sec: Gap duration to trigger person_left event (seconds)
        """
        self.camera_id = camera_id
        self.window_sec = window_sec
        self.gap_sec = gap_sec
        
        # State
        self._state = PresenceState.IDLE
        self._window_start: Optional[datetime] = None
        self._last_detection_time: Optional[datetime] = None
        self._session_start: Optional[datetime] = None
        
        # Accumulated stats for current window
        self._person_counts: list[int] = []
        self._confidences: list[float] = []
        self._last_frame: Optional[np.ndarray] = None
        self._is_first_window = True
    
    @property
    def state(self) -> PresenceState:
        """Current presence state."""
        return self._state
    
    def update(
        self,
        detections: list[Detection],
        frame: np.ndarray,
        current_time: Optional[datetime] = None
    ) -> Optional[VisionEvent]:
        """
        Update aggregator with new detections.
        
        Args:
            detections: List of detections from current frame
            frame: Current frame (for snapshot)
            current_time: Current timestamp (default: now)
        
        Returns:
            VisionEvent if an event should be emitted, None otherwise
        """
        now = current_time or datetime.now(timezone.utc)
        
        # Filter to only detections inside the zone
        inside_zone = [d for d in detections if d.is_inside_zone]
        has_person = len(inside_zone) > 0
        
        event: Optional[VisionEvent] = None
        
        if self._state == PresenceState.IDLE:
            if has_person:
                # Transition: IDLE -> PERSON_PRESENT
                self._state = PresenceState.PERSON_PRESENT
                self._window_start = now
                self._session_start = now
                self._last_detection_time = now
                self._is_first_window = True
                
                # Start accumulating
                self._person_counts = [len(inside_zone)]
                self._confidences = [d.confidence for d in inside_zone]
                self._last_frame = frame.copy()
                
                logger.debug(f"State: IDLE -> PERSON_PRESENT at {now}")
        
        elif self._state == PresenceState.PERSON_PRESENT:
            if has_person:
                # Continue accumulating
                self._last_detection_time = now
                self._person_counts.append(len(inside_zone))
                self._confidences.extend([d.confidence for d in inside_zone])
                self._last_frame = frame.copy()
                
                # Check if window is complete
                window_elapsed = (now - self._window_start).total_seconds()
                
                if window_elapsed >= self.window_sec:
                    # Emit event
                    event_type = "person_present_start" if self._is_first_window else "person_still_present"
                    event = self._create_event(now, event_type)
                    
                    # Reset window
                    self._window_start = now
                    self._person_counts = []
                    self._confidences = []
                    self._is_first_window = False
                    
                    logger.debug(f"Emitting {event_type} event")
            else:
                # No person detected - check gap
                gap_elapsed = (now - self._last_detection_time).total_seconds()
                
                if gap_elapsed >= self.gap_sec:
                    # Transition: PERSON_PRESENT -> IDLE
                    event = self._create_event(now, "person_left")
                    
                    # Reset state
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
        """Create a VisionEvent from accumulated stats."""
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
            frame_uri=""  # Will be filled by use case
        )
    
    def get_snapshot_frame(self) -> Optional[np.ndarray]:
        """Get the last captured frame for snapshot."""
        return self._last_frame
    
    def force_end_session(self, current_time: Optional[datetime] = None) -> Optional[VisionEvent]:
        """
        Force end current session (e.g., on application shutdown).
        
        Returns:
            VisionEvent if session was active, None otherwise
        """
        if self._state != PresenceState.PERSON_PRESENT:
            return None
        
        now = current_time or datetime.now(timezone.utc)
        event = self._create_event(now, "person_left")
        
        # Reset state
        self._state = PresenceState.IDLE
        self._window_start = None
        self._session_start = None
        self._last_detection_time = None
        self._person_counts = []
        self._confidences = []
        self._last_frame = None
        
        return event
