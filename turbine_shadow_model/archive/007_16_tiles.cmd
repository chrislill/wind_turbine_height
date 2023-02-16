SET experiment=007_16_tiles
SET data=v007_16_tiles
SET yolo_path=%USERPROFILE%/Code/yolov7
CALL CD %USERPROFILE%\Code\wind_turbine_height
CALL yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/train.py --img-size 640 --batch 4 --workers 4 --epochs 100 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp %yolo_path%/data/hyp.scratch.custom.yaml --data data/turbine_shadow_data/%data%/data.yaml --weights %yolo_path%/weights/yolov7_training.pt --name %experiment% --device 0