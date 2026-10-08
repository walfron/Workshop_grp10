generate_dataset.py : Utilisé pour créer une dataset pour entrainer le modèle aux anomalies
train_model.py : entraine le modèle choisi(Isolation Forest) sur la dataset et l'exporte sous format joblib
benchmark_yolo.py : le codage principale pour la partie vision qui exporte le modèle Yolov8n en ONNX
test_live.py,vision_service.py : test_live.py sert comme un script de test qui a comme fonction d'essayer l'activation du camera,plus precisement la camera intégrée du PC en utilisant la classe créée dans vision_service.py
stream_local.py : un autre code de test qui lie le webcam attaché au PC vers le dashboard,un simple test fait dans avec un webcam attaché à un PC au lieu de Raspberry pour mieux comprendre ce qu'il faut faire
stream_sentinel_finale.py : le script finale qui se fait et s'éxecute par terminal aprés liaison SSH avec Raspberry Pi 5,il gére le passage du webcam et l'alerte d'intrusion ainsi que l'alerte d'une anomalie chez le dashboard