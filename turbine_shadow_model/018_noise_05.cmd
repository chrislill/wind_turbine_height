SET experiment=023_noise_05
SET baseline=009_4_tiles
SET run=3
SET data=v015
SET yolo_path=%USERPROFILE%/Code/yolov7
:: SET weights_path=%yolo_path%/weights/yolov7_training.pt
SET weights_path=.\runs\train\%baseline%%run%\weights\best.pt
SET hyp_path=hyperparameters\hyp.default.yaml
:: SET hyp_path=hyp.no_shear.yaml

CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/train.py --epochs 200 --img-size 640 --batch 4 --workers 4 --cfg %yolo_path%/cfg/training/yolov7.yaml --hyp %hyp_path% --data ../data/turbine_shadow_data/%data%/data.yaml --weights %weights_path% --device 0 --name %experiment%
