import cv2
from vision_service import VisionDetector


def test_camera_stream(camera_index: int = 0):
    detector = VisionDetector(confidence_threshold=0.55, cooldown_sec=5)

    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"Erreur : Impossible d'ouvrir la caméra {camera_index}.")
        return

    print("Flux vidéo démarré. Appuie sur 'q' pour quitter.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape
        is_present, should_alert, conf, box = detector.detect_person(frame)

        if is_present:
            status_text = f"INTRUSION DETECTEE ({conf:.2f})"
            color = (0, 0, 255)  # Rouge continu

            # Conversion de la bounding box YOLO (640x640 -> repère frame 640x480)
            if box:
                cx, cy, bw, bh = box
                x1 = int((cx - bw / 2) * (w / 640.0))
                y1 = int((cy - bh / 2) * (h / 640.0))
                x2 = int((cx + bw / 2) * (w / 640.0))
                y2 = int((cy + bh / 2) * (h / 640.0))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            if should_alert:
                cv2.putText(frame, "[ALERTE RESEAU ENVOYEE]", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        else:
            status_text = f"NOMINAL ({conf:.2f})"
            color = (0, 255, 0)  # Vert

        cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.imshow("Sentinel-X - Vision Direct", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    test_camera_stream(camera_index=1)