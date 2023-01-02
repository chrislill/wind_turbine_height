SET experiment=016_tiles
SET version=
SET data=v009
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=%yolo_path%/weights/yolov7_training.pt
:: SET weights_path=.\runs\train\%experiment%%version%\weights\last.pt
SET hyp_path=turbine_shadow_model/data/hyp.scratch.custom.yaml
:: SET hyp_path=turbine_shadow_model/hyp.no_shear.yaml

CALL CD %USERPROFILE%\Code\wind_turbine_height
CALL yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/train.py --img-size 640 --batch 4 --workers 4 --epochs 100 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp %yolo_path%/data/hyp.scratch.custom.yaml --data data/turbine_shadow_data/%data%/data.yaml --weights $weights_path --device 0 --name %experiment%
