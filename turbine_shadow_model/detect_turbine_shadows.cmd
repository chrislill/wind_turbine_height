SET experiment=026_additional_labels_mixup
SET run=
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=.\runs\train\%experiment%%run%\weights\best.pt
SET image_file=
::SET weights_path=%yolo_path%/weights/yolov7-e6e.pt

SET image_path=..\data\turbine_shadow_data\v013\test\images
::SET image_path=..\data\turbine_shadow_data\active_learning\test\images

CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL python %yolo_path%/detect.py --conf 0.50 --weights %weights_path% --source %image_path%
