import cv2, numpy as np, streamlit as st, json, os
from ultralytics import YOLO
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import warnings; warnings.filterwarnings("ignore")

CONFIG_PATH = "resource/config/polygon.json"

def load_poly():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f: return json.load(f).get("active_area", [])
        except: return []
    return []

def save_poly(poly):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f: json.dump({"active_area": poly}, f)

st.set_page_config(layout="wide", page_title="YOLO Polygon")
model = YOLO("resource/weights/yolo11s.pt")
ss = st.session_state

# Init State
if 'bg' not in ss: ss.bg = None
if 'poly' not in ss: ss.poly = load_poly()
if 'canvas_key' not in ss: ss.canvas_key = 0

st.title("YOLO Polygon Detection")
c1, c2 = st.columns(2)

with c1:
    st.subheader("1. Zone Config")
    if st.button("Capture Background"):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, f = cap.read()
            if ret: 
                ss.bg = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                # Increment key to force canvas reset/refresh with OFF state or maintain state?
                # User complaint: "Capture 2nd time, drawing stays same".
                # If we want to EDIT existing JSON poly on NEW background, we should keep it.
                # If we want to CLEAR it, we should clear ss.poly.
                # User said: "Read/draw/change based on polygon.json".
                # So we should LOAD from JSON (or keep current) and let them edit.
                # To ensure the canvas *re-renders* with the new background and correct poly,
                # we force a key update.
                ss.canvas_key += 1
        cap.release()

    bg_img = Image.fromarray(ss.bg) if ss.bg is not None else None
    
    # Prepare initial drawing for canvas from ss.poly
    initial_drawing = None
    if ss.poly:
        # Fabric.js format
        initial_drawing = {
            "version": "4.4.0",
            "objects": [{
                "type": "path",
                "path": [['M', p[0], p[1]] if i==0 else ['L', p[0], p[1]] for i, p in enumerate(ss.poly)] + [['z']],
                "stroke": "#F00", "strokeWidth": 2, "fill": "rgba(255, 165, 0, 0.3)"
            }]
        }

    c = st_canvas(
        fill_color="rgba(255,165,0,0.3)", 
        stroke_color="#F00", 
        background_image=bg_img, 
        height=480, width=640, 
        drawing_mode="polygon", 
        initial_drawing=initial_drawing if ss.bg is not None else None,
        key=f"c_{ss.canvas_key}", # Dynamic key to force re-render on capture
        update_streamlit=True
    )
    
    if c.json_data and c.json_data["objects"]:
        # Check if user drew something new
        new_poly = []
        for o in c.json_data["objects"]:
            if o["type"] == "path":
                pts = [[int(p[1]), int(p[2])] for p in o["path"] if p[0] in ['M','L']]
                if len(pts) > 2: new_poly = pts; break
        
        # Only update if changed (simple check)
        if new_poly and new_poly != ss.poly:
            ss.poly = new_poly
            save_poly(ss.poly)
            # st.toast("Polygon saved!") 

with c2:
    st.subheader("2. Run Detection (MAX 15 FPS)")
    run = st.checkbox("Run", value=True)
    window = st.image([])
    
    if run:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        while cap.isOpened() and run:
            import time
            t0 = time.time()
            ret, frame = cap.read()
            if not ret: break
            
            frame = cv2.resize(frame, (640, 480))
            # Clean frame inference
            res = model(frame, classes=[0], conf=0.5, verbose=False, imgsz=640)
            view = frame.copy()
            
            # Reload poly dynamically? No, use session state which is updated by Left column.
            # But if JSON changes externally? We stick to session state logic for now.
            
            if len(ss.poly) > 2:
                cv2.polylines(view, [np.array(ss.poly, np.int32)], True, (255,255,0), 2)
            
            if res:
                for b in res[0].boxes.xyxy.cpu().numpy().astype(int):
                    center = (int((b[0]+b[2])/2), int((b[1]+b[3])/2))
                    inside = False
                    if len(ss.poly) > 2:
                        inside = cv2.pointPolygonTest(np.array(ss.poly, np.int32), center, False) >= 0
                    cv2.rectangle(view, (b[0],b[1]), (b[2],b[3]), (0,0,255) if inside else (0,255,0), 2)
            
            window.image(cv2.cvtColor(view, cv2.COLOR_BGR2RGB))
            time.sleep(max(0, 1/15 - (time.time()-t0)))
        cap.release()
