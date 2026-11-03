@echo off
REM One-time install of FaceFusion deps (face restore for Siri reels). Needs git, Python 3.10-3.12 and ffmpeg on PATH.
cd /d D:\telugucouple\tools
if not exist facefusion git clone https://github.com/facefusion/facefusion
cd facefusion
python install.py cuda@12 --skip-conda
echo.
echo Install finished. If worker.bat is already open, close it and start it again.
pause
