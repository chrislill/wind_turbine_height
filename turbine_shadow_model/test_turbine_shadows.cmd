SET experiment=012_baseline
SET run=3
SET data=v013
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=.\runs\train\%experiment%%run%\weights\best.pt

CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL python %yolo_path%/test.py --conf 0.5 --iou 0.5 --batch 4 --task test --save-txt --save-json --data ../data/turbine_shadow_data/%data%/data.yaml --weights %weights_path% --device 0 --name %experiment%
