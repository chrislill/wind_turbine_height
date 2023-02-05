SET experiment=012_baseline
SET baseline=009_4_tiles
SET run=4
SET data=v009_4_tiles
SET yolo_path=%USERPROFILE%/Code/yolov7
:: SET weights_path=%yolo_path%/weights/yolov7_training.pt
SET weights_path=.\runs\train\%baseline%%run%\weights\last.pt
SET hyp_path=hyp.scratch.custom.yaml
:: SET hyp_path=hyp.no_shear.yaml

CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
:: CALL wandb disabled
CALL python %yolo_path%/train.py --epochs 300 --img-size 640 --batch 4 --workers 4 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp %hyp_path% --data ../data/turbine_shadow_data/%data%/data.yaml --weights %weights_path% --device 0 --name %experiment% --entity data_science_msc --project turbine_shadow
