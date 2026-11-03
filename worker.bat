@echo off
REM Couple GPU worker (Satyam & Padma): watches D:\telugucouple\jobs for *.json and runs FaceFusion on the RTX 3050. Leave this window open.
REM CUDA 12 / cuDNN 9 DLLs from pip (nvidia-*-cu12) so onnxruntime uses the GPU instead of the CPU
set NV=%APPDATA%\Python\Python312\site-packages\nvidia
set PATH=%NV%\cublas\bin;%NV%\cudnn\bin;%NV%\cuda_runtime\bin;%NV%\cufft\bin;%NV%\curand\bin;%NV%\cuda_nvrtc\bin;%PATH%
cd /d D:\telugucouple\tools
python -c "import onnxruntime as o; print('providers:', o.get_available_providers())"
python worker.py
pause
