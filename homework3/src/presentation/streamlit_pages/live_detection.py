"""Trang Phát hiện Trực tiếp - Luồng Camera với suy luận YOLO và cấu hình vùng cấm."""
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
    """Hiển thị trang phát hiện trực tiếp."""
    
    st.header("🎥 Phát hiện Trực tiếp")
    st.markdown("Phát hiện người theo thời gian thực với giám sát vùng cấm")
    
    # Khởi tạo session state
    ss = st.session_state
    if 'bg' not in ss:
        ss.bg = None
    if 'canvas_key' not in ss:
        ss.canvas_key = 0
    if 'polygon' not in ss:
        ss.polygon = config.polygon
    
    # Bố cục: hai cột
    col_config, col_stream = st.columns([1, 1])
    
    # === Cột 1: Cấu hình ===
    with col_config:
        st.subheader("📐 Cấu hình Vùng cấm")
        
        # Chỉ báo trạng thái
        status_cols = st.columns(2)
        with status_cols[0]:
            minio_status = "🟢 Đã kết nối" if minio_repo and minio_repo.is_connected else "🔴 Ngoại tuyến"
            st.metric("MinIO", minio_status)
        with status_cols[1]:
            rabbit_status = "🟢 Đã kết nối" if rabbitmq_pub and rabbitmq_pub.is_connected else "🔴 Ngoại tuyến"
            st.metric("RabbitMQ", rabbit_status)
        
        st.divider()
        
        # Chụp ảnh nền
        if st.button("📸 Chụp ảnh nền"):
            import platform
            # Thêm độ trễ để đảm bảo giải phóng tài nguyên nếu đang chạy stream
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
                    # Đặt lại polygon khi chụp nền mới để buộc vẽ lại
                    ss.polygon = [] 
                    st.success("Đã chụp ảnh nền! Hãy vẽ một vùng cấm mới.")
                
                # Giải phóng tài nguyên camera
                cap.release()
            else:
                st.error("Không thể mở camera!")
        
        # Canvas để vẽ polygon
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
        
        # Xử lý kết quả canvas
        # Xử lý kết quả canvas
        if canvas_result.json_data and canvas_result.json_data["objects"]:
            # Phân tích điểm polygon từ canvas
            new_poly = []
            for obj in canvas_result.json_data["objects"]:
                if obj["type"] == "path":
                    pts = [[int(p[1]), int(p[2])] for p in obj["path"] if p[0] in ['M', 'L']]
                    if len(pts) > 2:
                        new_poly = pts
                        break
            
            if new_poly and new_poly != ss.polygon:
                logger.info(f"Phát hiện cập nhật polygon. Cũ: {len(ss.polygon)} điểm, Mới: {len(new_poly)} điểm")
                ss.polygon = new_poly
                # Lưu polygon vào tệp
                save_polygon(ss.polygon)
                logger.info("Đã lưu polygon thành công.")
                st.success(f"✅ Đã lưu polygon: {len(new_poly)} điểm")
        
        # Thông tin polygon hiện tại
        if ss.polygon:
            st.info(f"Polygon hiện tại: {len(ss.polygon)} điểm")
        else:
            st.warning("Chưa xác định polygon. Hãy vẽ trên canvas ở trên.")
    
    # === Cột 2: Luồng Trực tiếp ===
    with col_stream:
        st.subheader("📺 Suy luận Thời gian thực")
        
        run_detection = st.checkbox("▶️ Bắt đầu Phát hiện", value=False)
        
        if run_detection:
            _run_detection_loop(config, ss, minio_repo, rabbitmq_pub)
        else:
            st.info("Chọn 'Bắt đầu Phát hiện' để bắt đầu luồng trực tiếp.")
            
            # Hiển thị khung hình mẫu nếu có
            if ss.bg is not None:
                st.image(ss.bg, caption="Khung hình chụp gần nhất", use_column_width=True)


def _run_detection_loop(config, ss, minio_repo, rabbitmq_pub):
    """Chạy vòng lặp phát hiện."""
    
    # Import lười biếng để tránh yêu cầu ultralytics khi khởi động ứng dụng
    from src.presentation.detector import PersonDetector
    from src.application.event_aggregator import EventAggregator
    from src.application.use_cases import HandleVisionEventUseCase
    
    # Khởi tạo detector
    # Kiểm tra xem detector đã có trong session state chưa để tránh tải lại
    if 'detector' not in ss:
        # Khởi tạo PersonDetector
        logger.info("Đang khởi tạo PersonDetector...")
        ss.detector = PersonDetector(
            model_path=config.model_path,
            conf_threshold=config.conf_threshold,
            polygon=ss.polygon
        )
        logger.info("PersonDetector đã được khởi tạo và lưu cache.")

    # Sử dụng lại detector đã cache
    detector = ss.detector
    
    # Luôn cập nhật polygon phòng trường hợp nó thay đổi
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
    
    # Các thành phần giao diện người dùng
    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    metrics_cols = st.columns(4)
    
    # Sử dụng CAP_ANY để ổn định hơn khi tải lại, DSHOW có thể bị crash khi giải phóng
    backend = cv2.CAP_ANY
    
    cap = None
    max_retries = 5
    for attempt in range(max_retries):
        cap = cv2.VideoCapture(config.camera_index, backend)
        if not cap.isOpened():
            # Dự phòng
            cap = cv2.VideoCapture(config.camera_index)
        
        if cap.isOpened():
            break
            
        if attempt < max_retries - 1:
            logger.warning(f"Camera đang bận, thử lại sau 1s... ({attempt+1}/{max_retries})")
            time.sleep(1.0)
            
    if cap is None or not cap.isOpened():
        st.error(f"❌ Không thể mở camera index {config.camera_index} sau {max_retries} lần thử")
        return
    
    frame_count = 0
    target_fps = getattr(config, 'target_fps', 15)
    event_count = 0
    consecutive_failures = 0
    
    # Vòng lặp phát hiện chính
    while cap.isOpened():
        t_start = time.time()
        ret, frame = cap.read()
        
        if not ret:
            consecutive_failures += 1
            if consecutive_failures > 20: # Dừng nếu thất bại trong khoảng 1-2 giây
                logger.error("Quá nhiều lần lỗi camera liên tiếp. Dừng stream.")
                st.error("Mất kết nối camera. Vui lòng kiểm tra kết nối hoặc thử lại.")
                break
            time.sleep(0.1)
            continue
        
        consecutive_failures = 0
        frame_count += 1
        frame = cv2.resize(frame, (640, 480))
        
        # Suy luận
        detections = []
        if frame_count % config.infer_every_n == 0:
            # Chạy phát hiện
            detections = detector.detect(frame)
            
            # Tổng hợp
            event = aggregator.update(detections, frame)
            if event:
                snapshot = aggregator.get_snapshot_frame()
                use_case.execute(event, snapshot)
                event_count += 1
                st.toast(f"🔔 Sự kiện: {event.event_type}", icon="🔔")
        
        # Trực quan hóa
        display_frame = detector.draw_detections(frame, detections)
        
        # Cập nhật UI
        fps = 1.0 / (time.time() - t_start + 1e-6)
        
        with metrics_cols[0]:
            st.metric("Trạng thái", aggregator.state.value)
        with metrics_cols[1]:
            st.metric("Phát hiện", len(detections))
        with metrics_cols[2]:
            st.metric("FPS", f"{fps:.1f}")
        with metrics_cols[3]:
            st.metric("Sự kiện", event_count)
        
        frame_placeholder.image(
            cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB),
            use_column_width=True
        )
        
        # Giới hạn tốc độ
        time.sleep(max(0, 1/target_fps - (time.time() - t_start)))
    
    # Dọn dẹp sau vòng lặp (thay thế khối finally)
    if cap is not None:
        # Giải phóng camera
        cap.release()
    
    # Xả (flush) khi đóng
    final_event = aggregator.force_end_session()
    if final_event:
        snapshot = aggregator.get_snapshot_frame()
        use_case.execute(final_event, snapshot)
    use_case.flush()
    
    st.info("Đã dừng phát hiện.")
