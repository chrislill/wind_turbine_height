SET experiment=002_baseline
SET run=
SET data=v002
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=.\runs\train\%experiment%%run%\weights\best.pt

CALL CD %USERPROFILE%\Code\wind_turbine_height\hub_shadow_model
CALL ..\yolov7_venv\scripts\activate
:: CALL wandb disabled
CALL python %yolo_path%/test.py --conf 0.2 --iou 0.5 --batch 4 --task test --save-txt --save-json --data ../data/hub_shadow_data/%data%/data.yaml --weights %weights_path% --device 0 --name %experiment%
