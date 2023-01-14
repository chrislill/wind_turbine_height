SET experiment=001_initial_model
SET run=1
SET data=v001
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=.\runs\train\%experiment%%run%\weights\best.pt
SET image_file=almendarache_png.rf.66c76fdb89707ab8223492f51c83e1af.jpg
::SET weights_path=%yolo_path%/weights/yolov7-e6e.pt
::SET image_file=man_cafe.jpg
SET image_path=..\data\hub_shadow_data\%data%\test\images\%image_file%


CALL CD %USERPROFILE%\Code\wind_turbine_height\hub_height_model
CALL ..\yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/detect.py --conf 0.60 --weights %weights_path% --source %image_path%
