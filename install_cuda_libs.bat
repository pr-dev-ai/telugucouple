@echo off
REM One-time: CUDA 12 + cuDNN 9 runtime DLLs so FaceFusion runs on the RTX 3050 (about 2-3 GB download)
python -m pip install --user nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cuda-nvrtc-cu12
echo.
echo Done. Close this window, close the old worker window, then double-click worker.bat
pause
