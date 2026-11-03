"""Launch FaceFusion with onnxruntime's CUDA/cuDNN DLLs preloaded (pip nvidia-*-cu12), so the CUDA provider really loads."""
import os, sys, pathlib, runpy
try:
    import onnxruntime as ort
    if hasattr(ort, "preload_dlls"): ort.preload_dlls()
except Exception as e:
    print("preload_dlls failed:", e, flush=True)
FF = str(pathlib.Path(__file__).resolve().parent / "facefusion")
os.chdir(FF); sys.path.insert(0, FF)          # facefusion imports its own package from its folder
sys.argv = ["facefusion.py", *sys.argv[1:]]
runpy.run_path(str(pathlib.Path(__file__).resolve().parent / "facefusion" / "facefusion.py"), run_name="__main__")
