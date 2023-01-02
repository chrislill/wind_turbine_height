SET experiment=008_no_mosaic
SET data=v007_16_tiles
SET yolo_path=%USERPROFILE%/Code/yolov7
CALL CD %USERPROFILE%\Code\wind_turbine_height
CALL yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/train.py --img-size 640 --batch 4 --workers 4 --epochs 25 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp turbine_shadow_model/hyp.no_modifications.yaml --data data/turbine_shadow_data/%data%/data.yaml --weights %yolo_path%/weights/yolov7_training.pt --name %experiment% --device 0