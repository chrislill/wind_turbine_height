SET experiment=031_translate_10
SET baseline=009_4_tiles
SET run=3
SET data=v013
SET yolo_path=%USERPROFILE%/Code/yolov7
SET hyp_path=hyperparameters\hyp.translate_10.yaml

SET weights_path=.\runs\train\%baseline%%run%\weights\best.pt
:: SET weights_path=.\runs\train\%experiment%\weights\last.pt

CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/train.py --epochs 200 --img-size 640 --batch 4 --workers 4 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp %hyp_path% --data ../data/turbine_shadow_data/%data%/data.yaml --weights %weights_path% --device 0 --name %experiment%
:: --resume