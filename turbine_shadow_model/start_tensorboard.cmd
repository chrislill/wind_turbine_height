CALL CD %USERPROFILE%\Code\wind_turbine_height\turbine_shadow_model
CALL ..\yolov7_venv\scripts\activate
CALL tensorboard --logdir turbine_shadow
