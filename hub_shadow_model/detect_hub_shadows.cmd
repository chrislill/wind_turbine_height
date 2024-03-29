SET experiment=015_active_learning
SET run=
SET data=all_unlabelled_images
SET dataset=test
SET yolo_path=%USERPROFILE%/Code/yolov7
SET weights_path=.\runs\train\%experiment%%run%\weights\best.pt
::SET weights_path=%yolo_path%/weights/yolov7-e6e.pt
::SET image_file=man_cafe.jpg
SET image_path=..\data\hub_shadow_data\%data%\%dataset%\images


CALL CD %USERPROFILE%\Code\wind_turbine_height\hub_height_model
CALL ..\yolov7_venv\scripts\activate
CALL wandb disabled
CALL python %yolo_path%/detect.py --conf 0.50 --weights %weights_path% --source %image_path% --name %dataset%--save-txt --save-conf
