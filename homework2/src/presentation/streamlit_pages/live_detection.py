"""Live Detection Page - Camera feed with YOLO inference and polygon config."""
import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import time
import logging

from src.infrastructure.config import save_polygon

logger = logging.getLogger(__name__)


def render_live_detection(config, minio_repo, rabbitmq_pub):
    """Render the live detection page."""
    
    st.header("🎥 Live Detection")
    st.markdown("Real-time person detection with forbidden zone monitoring")
    
    # Session state init
    ss = st.session_state
    if 'bg' not in ss:
        ss.bg = None
    if 'canvas_key' not in ss:
        ss.canvas_key = 0
    if 'polygon' not in ss:
        ss.polygon = config.polygon
    
    # Layout: two columns
    col_config, col_stream = st.columns([1, 1])
    
    # === Column 1: Configuration ===
    with col_config:
        st.subheader("📐 Forbidden Zone Configuration")
        
        # Status indicators
        status_cols = st.columns(2)
        with status_cols[0]:
            minio_status = "🟢 Connected" if minio_repo and minio_repo.is_connected else "🔴 Offline"
            st.metric("MinIO", minio_status)
        with status_cols[1]:
            rabbit_status = "🟢 Connected" if rabbitmq_pub and rabbitmq_pub.is_connected else "🔴 Offline"
            st.metric("RabbitMQ", rabbit_status)
        
        st.divider()
        
        # Capture background
        if st.button("📸 Capture Background Frame"):
            import platform
            # Add delay to ensure resource release if streaming was active
            time.sleep(0.5)
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
            cap = cv2.VideoCapture(config.camera_index, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(config.camera_index)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    ss.bg = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    ss.canvas_key += 1
                    st.success("Background captured!")
                cap.release()
            else:
                st.error("Cannot open camera!")
        
        # Canvas for polygon drawing
        bg_img = Image.fromarray(ss.bg) if ss.bg is not None else None
        
        initial_drawing = None
        if ss.polygon:
            initial_drawing = {
                "version": "4.4.0",
                "objects": [{
                    "type": "path",
                    "path": [['M', p[0], p[1]] if i == 0 else ['L', p[0], p[1]] 
                             for i, p in enumerate(ss.polygon)] + [['z']],
                    "stroke": "#FF0000",
                    "strokeWidth": 3,
                    "fill": "rgba(255, 0, 0, 0.2)"
                }]
            }
        
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.2)",
            stroke_color="#FF0000",
            stroke_width=3,
            background_image=bg_img,
            height=360,
            width=480,
            drawing_mode="polygon",
            initial_drawing=initial_drawing if ss.bg is not None else None,
            key=f"canvas_{ss.canvas_key}",
            update_streamlit=True
        )
        
        # Process canvas result
        if canvas_result.json_data and canvas_result.json_data["objects"]:
            new_poly = []
            for obj in canvas_result.json_data["objects"]:
                if obj["type"] == "path":
                    pts = [[int(p[1]), int(p[2])] for p in obj["path"] if p[0] in ['M', 'L']]
                    if len(pts) > 2:
                        new_poly = pts
                        break
            
            if new_poly and new_poly != ss.polygon:
                ss.polygon = new_poly
                try:
                    save_polygon(ss.polygon)
                    st.success(f"✅ Polygon saved: {len(new_poly)} points")
                except Exception as e:
                    logger.error(f"Failed to save polygon: {e}")
                    st.error(f"❌ Failed to save polygon: {e}")
        
        # Current polygon info
        if ss.polygon:
            st.info(f"Current polygon: {len(ss.polygon)} points")
        else:
            st.warning("No polygon defined. Draw on the canvas above.")
    
    # === Column 2: Live Stream ===
    with col_stream:
        st.subheader("📺 Real-time Inference")
        
        run_detection = st.checkbox("▶️ Start Detection", value=False)
        
        if run_detection:
            _run_detection_loop(config, ss, minio_repo, rabbitmq_pub)
        else:
            st.info("Check 'Start Detection' to begin live stream.")
            
            # Show sample frame if available
            if ss.bg is not None:
                st.image(ss.bg, caption="Last captured frame", use_column_width=True)


def _run_detection_loop(config, ss, minio_repo, rabbitmq_pub):
    """Run the detection loop."""
    
    # Lazy imports to avoid requiring ultralytics at app startup
    from src.presentation.detector import PersonDetector
    from src.application.event_aggregator import EventAggregator
    from src.application.use_cases import HandleVisionEventUseCase
    
    # Initialize detector
    # Initialize detector directly (no caching to avoid thread-safety/fusion issues)
    # This fixes the "AttributeError: 'Conv' object has no attribute 'bn'"
    detector = PersonDetector(
        model_path=config.model_path,
        conf_threshold=config.conf_threshold,
        polygon=ss.polygon
    )
    detector.set_polygon(ss.polygon)
    
    aggregator = EventAggregator(
        camera_id=config.camera_id,
        window_sec=config.emit_every_sec,
        gap_sec=config.session_gap_sec
    )
    
    use_case = HandleVisionEventUseCase(
        minio_repo=minio_repo,
        rabbitmq_pub=rabbitmq_pub,
        snapshot_prefix=config.s3_prefix_snapshots,
        events_prefix=config.s3_prefix_events,
        jpeg_quality=config.snapshot_jpeg_quality
    )
    
    # UI elements
    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    metrics_cols = st.columns(4)
    
    # Use CAP_DSHOW on Windows for better stability
    import platform
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    
    cap = cv2.VideoCapture(config.camera_index, backend)
    
    if not cap.isOpened():
        # Fallback to default backend if DSHOW fails
        cap = cv2.VideoCapture(config.camera_index)
        if not cap.isOpened():
            st.error(f"❌ Cannot open camera index {config.camera_index}")
            return
    
    frame_count = 0
    target_fps = getattr(config, 'target_fps', 15)
    event_count = 0
    consecutive_failures = 0
    
    try:
        while cap.isOpened():
            t_start = time.time()
            ret, frame = cap.read()
            
            if not ret:
                consecutive_failures += 1
                if consecutive_failures > 20: # Stop if failed for ~1-2 seconds
                    logger.error("Too many consecutive camera failures. Stopping stream.")
                    st.error("Camera stream lost. Please check connection or try again.")
                    break
                time.sleep(0.1)
                continue
            
            consecutive_failures = 0
            frame_count += 1
            frame = cv2.resize(frame, (640, 480))
            
            # Inference
            detections = []
            if frame_count % config.infer_every_n == 0:
                try:
                    detections = detector.detect(frame)
                    
                    # Aggregate
                    event = aggregator.update(detections, frame)
                    if event:
                        snapshot = aggregator.get_snapshot_frame()
                        use_case.execute(event, snapshot)
                        event_count += 1
                        st.toast(f"🔔 Event: {event.event_type}", icon="🔔")
                except Exception as e:
                    logger.error(f"Inference error: {e}")
            
            # Visualization
            display_frame = detector.draw_detections(frame, detections)
            
            # Update UI
            fps = 1.0 / (time.time() - t_start + 1e-6)
            
            with metrics_cols[0]:
                st.metric("State", aggregator.state.value)
            with metrics_cols[1]:
                st.metric("Detections", len(detections))
            with metrics_cols[2]:
                st.metric("FPS", f"{fps:.1f}")
            with metrics_cols[3]:
                st.metric("Events", event_count)
            
            frame_placeholder.image(
                cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB),
                use_column_width=True
            )
            
            # Rate limiting
            time.sleep(max(0, 1/target_fps - (time.time() - t_start)))
            
    except Exception as e:
        logger.exception("Detection loop error")
        st.error(f"Error: {e}")
    finally:
        if cap is not None:
            cap.release()
        
        # Flush on close
        try:
            final_event = aggregator.force_end_session()
            if final_event:
                snapshot = aggregator.get_snapshot_frame()
                use_case.execute(final_event, snapshot)
            use_case.flush()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        st.info("Detection stopped.")
