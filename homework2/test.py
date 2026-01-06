import cv2, numpy as np, time
from ultralytics import YOLO

cap, win = cv2.VideoCapture(0), "Test"
model = YOLO("yolo11s.pt")
poly, temp = [], []

def on_mouse(e, x, y, f, p):
    global poly, temp
    if e == cv2.EVENT_LBUTTONDOWN: temp.append([x, y])
    elif e == cv2.EVENT_RBUTTONDOWN and len(temp) > 2: poly, temp = list(temp), []

cv2.namedWindow(win); cv2.setMouseCallback(win, on_mouse)

while cap.isOpened():
    t0 = time.time()
    ret, frame = cap.read()
    if not ret: break
    
    # Detect (Directly using simple ultralytics API)
    results = model(frame, classes=[0], conf=0.6, verbose=False, imgsz=640)
    bboxes = results[0].boxes.xyxy.cpu().numpy().astype(int) if len(results) > 0 else []

    # Draw Polygon
    if temp: cv2.polylines(frame, [np.array(temp, np.int32)], False, (0,0,255), 2)
    if poly: cv2.polylines(frame, [np.array(poly, np.int32)], True, (255,255,0), 2)
    
    # Check & Draw BBoxes
    for box in bboxes:
        center = (float((box[0]+box[2])/2), float((box[1]+box[3])/2))
        inside = len(poly) > 2 and cv2.pointPolygonTest(np.array(poly, np.int32), center, False) >= 0
        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0,0,255) if inside else (0,255,0), 2)

    cv2.imshow(win, frame)
    # Limit to ~15 FPS
    wait_ms = max(1, int(1000/15 - (time.time()-t0)*1000))
    if cv2.waitKey(wait_ms) == ord('q'): break

cap.release(); cv2.destroyAllWindows()
