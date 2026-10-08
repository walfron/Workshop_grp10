import time
import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path
from ultralytics import YOLO

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
ONNX_PATH = MODELS_DIR / "yolov8n.onnx"


def export_to_onnx():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not ONNX_PATH.exists():
        print("Export de YOLOv8n vers ONNX...")
        model = YOLO("yolov8n.pt")
        model.export(format="onnx", imgsz=640, optimise=True)
        exported_file = Path("yolov8n.onnx")
        if exported_file.exists():
            exported_file.rename(ONNX_PATH)


def run_benchmark(device_index: int = 1, num_frames: int = 150):
    export_to_onnx()

    session = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    cap = cv2.VideoCapture(device_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"Erreur : Impossible d'ouvrir la webcam (index {device_index}).")
        return

    print(f"Début du benchmark sur {num_frames} frames en 640x480...")
    latencies = []

    for _ in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break

        start_time = time.perf_counter()

        img = cv2.resize(frame, (640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.transpose((2, 0, 1)).astype(np.float32) / 255.0
        img = np.expand_dims(img, axis=0)

        _ = session.run(None, {input_name: img})
        latencies.append(time.perf_counter() - start_time)

    cap.release()
    avg_latency = np.mean(latencies)
    fps = 1.0 / avg_latency
    print(f"Latence moyenne par frame : {avg_latency * 1000:.2f} ms")
    print(f"Débit estimé : {fps:.2f} FPS")


if __name__ == "__main__":
    run_benchmark()