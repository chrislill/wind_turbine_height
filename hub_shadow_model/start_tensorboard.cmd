CALL CD %USERPROFILE%\Code\wind_turbine_height\hub_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL tensorboard --logdir runs/train
