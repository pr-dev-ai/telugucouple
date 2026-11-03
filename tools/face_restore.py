"""Queue a FaceFusion job for the GPU worker and wait: python face_restore.py reels/<folder>  (uses motion.mp4 or replace.mp4)"""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
d = pathlib.Path(sys.argv[1]).resolve(); rel = d.relative_to(ROOT)
src = next(p for p in ["motion.mp4", "replace.mp4"] if (d / p).exists())
job = ROOT / "jobs" / f"{d.name}_restore.json"
job.write_text(json.dumps({"type": "face_restore", "source": "identity/v1/hero.png",
                           "target": f"{rel}/{src}", "output": f"{rel}/restored.mp4"}, indent=1))
print("queued", job.name, "(worker.bat must be running on the PC)")
for _ in range(360):
    if job.with_suffix(".done").exists(): print("restored:", d / "restored.mp4"); sys.exit(0)
    if job.with_suffix(".err").exists(): print("ERROR:", job.with_suffix(".err").read_text()[-800:]); sys.exit(1)
    time.sleep(5)
print("timed out waiting for the worker"); sys.exit(2)
