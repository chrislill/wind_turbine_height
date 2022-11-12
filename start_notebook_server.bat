@echo off
title Jupyter notebook server
echo Jupyter notebook server for amun_analytics project

REM Start the python environment
call venv\Scripts\activate.bat

REM Set the PYTHONPATH within the venv
set PYTHONPATH=%cd%
call jupyter notebook
pause
