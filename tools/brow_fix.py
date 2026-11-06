"""Smooth the skin between the eyebrows (glabella) in every frame: removes Kling frown-crease artifacts.
   python brow_fix.py in.mp4 out.mp4"""
import sys, cv2, numpy as np
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', allowed_modules=['detection'], providers=['CPUExecutionProvider']); app.prepare(ctx_id=-1, det_size=(320, 320))
cap = cv2.VideoCapture(sys.argv[1]); fps = cap.get(5); W, H = int(cap.get(3)), int(cap.get(4))
out = cv2.VideoWriter(sys.argv[2] + ".tmp.mp4", cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H)); last = None; n = 0
while True:
    ok, f = cap.read()
    if not ok: break
    fs = app.get(f)
    if fs: last = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0]))
    if last is not None:
        le, re = last.kps[0], last.kps[1]; d = np.linalg.norm(re - le)
        mid = (le + re) / 2; up = np.array([-(re-le)[1], (re-le)[0]]) / d       # perpendicular, pointing up the face
        if up[1] > 0: up = -up
        c = mid + up * d * 0.42
        ax = (int(d * 0.30), int(d * 0.30)); ang = np.degrees(np.arctan2((re-le)[1], (re-le)[0]))
        m = np.zeros((H, W), np.float32); cv2.ellipse(m, (int(c[0]), int(c[1])), ax, ang, 0, 360, 1.0, -1)
        k = max(3, int(d * 0.25) | 1); m = cv2.GaussianBlur(m, (k, k), 0)[..., None]
        # smooth skin but keep tone: strong bilateral + light blur, then blend inside the soft mask
        sm = cv2.bilateralFilter(f, 9, 40, 9); sm = cv2.GaussianBlur(sm, (0, 0), d * 0.06)
        f = (f * (1 - m) + sm * m).astype(np.uint8)
    out.write(f); n += 1
out.release(); print("frames", n)
import subprocess; subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", sys.argv[2] + ".tmp.mp4", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", sys.argv[2]], check=True)
