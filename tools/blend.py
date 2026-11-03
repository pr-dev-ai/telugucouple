"""Blend pass: make the dancer(s) sit IN the room instead of on top of it. Runs on the PC (GPU onnxruntime), no API cost.

  python blend.py <in.mp4> <out.mp4> [--strength 0.4] [--bg-blur 0] [--wrap 0.35] [--still]
  python blend.py <in.png> <out.png> ...           (same on a still, for checking)

Per frame:
  1. person mask with u2net_human_seg (~/.u2net, already on the PC), temporally smoothed so edges do not flicker
  2. colour/exposure harmonisation: the person's LAB mean is pulled part of the way toward the room right around them
     (a ring outside the mask): L by strength*0.75 (capped), a/b by strength, chroma spread toward the room's; stats are EMA-smoothed
  3. light wrap: the blurred room light bleeds onto the person's edges (what a real lens does)
  4. optional background defocus (--bg-blur sigma px at 720 wide) for close framings, mask-aware so the person does not halo
Prints before/after numbers: dL (person vs room brightness) and chroma ratio (person vs room saturation).
"""
import argparse, pathlib, subprocess, sys
import cv2
import numpy as np

MODEL = pathlib.Path.home() / ".u2net" / "u2net_human_seg.onnx"
_sess = None


def sess():
    global _sess
    if _sess is None:
        import onnxruntime as ort
        try:
            if hasattr(ort, "preload_dlls"): ort.preload_dlls()
        except Exception:
            pass
        _sess = ort.InferenceSession(str(MODEL), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    return _sess


def person_mask(bgr):
    h, w = bgr.shape[:2]
    x = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), (320, 320), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    x = x / max(1.0, x.max())
    x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    x = x.transpose(2, 0, 1)[None]
    s = sess()
    out = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / max(1e-6, out.max() - out.min())
    m = cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)
    m = np.clip((m - 0.25) / 0.5, 0, 1)                      # firm up the core, keep a soft edge
    return cv2.GaussianBlur(m, (0, 0), max(1.0, w / 480))


def lab(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)


def stats(L, sel):
    v = L[sel]
    if len(v) < 500:
        return None
    mu = v.mean(0)
    chroma = np.sqrt((v[:, 1] - 128) ** 2 + (v[:, 2] - 128) ** 2).mean()
    return mu, chroma


class Blender:
    def __init__(self, strength=0.4, bg_blur=0.0, wrap=0.35):
        self.k, self.bg_blur, self.wrap = strength, bg_blur, wrap
        self.m_prev = None; self.p = None; self.r = None
        self.before = []; self.after = []

    def frame(self, bgr):
        h, w = bgr.shape[:2]
        m = person_mask(bgr)
        if self.m_prev is not None:
            m = 0.65 * m + 0.35 * self.m_prev               # temporal smoothing against edge flicker
        self.m_prev = m
        core = m > 0.6
        ring = (cv2.dilate((m > 0.3).astype(np.uint8), np.ones((int(w * 0.08),) * 2, np.uint8)) > 0) & (m < 0.1)
        if ring.sum() < 2000:
            ring = m < 0.1
        L = lab(bgr)
        sp, sr = stats(L, core), stats(L, ring)
        if sp is None or sr is None:
            return bgr
        a = 0.15                                             # EMA so the grade does not pump frame to frame
        self.p = sp if self.p is None else tuple(a * np.array(x) + (1 - a) * np.array(y) for x, y in zip(sp, self.p))
        self.r = sr if self.r is None else tuple(a * np.array(x) + (1 - a) * np.array(y) for x, y in zip(sr, self.r))
        (mp, cp), (mr, cr) = self.p, self.r
        self.before.append((mp[0] - mr[0], cp / max(1, cr)))
        # 1) exposure + white balance pull toward the room
        # brightness: person vs room means compare different materials (green saree vs cream wall), so only ever pull a
        # person who is BRIGHTER than the room down a little (front-lit pop); never brighten
        dL = float(np.clip((mr[0] - mp[0]) * self.k * 0.5, -8, 0))
        dab = (mr[1:] - 128) * self.k * 0.6                    # take on the room's colour cast
        P = L.copy()
        P[..., 0] += dL
        # 2) chroma: if the person is much more saturated than the room, pull it in a bit (never boost)
        ratio = cp / max(1, cr)
        cs = 1.0 if ratio <= 1.6 else 1.0 - self.k * 0.35 * min(1.0, (ratio - 1.6) / 2.0)
        P[..., 1] = 128 + (P[..., 1] - 128) * cs + dab[0]
        P[..., 2] = 128 + (P[..., 2] - 128) * cs + dab[1]
        person = cv2.cvtColor(np.clip(P, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        room = bgr.astype(np.float32)
        # 3) light wrap: room light bleeding onto the silhouette edge
        inv = (1 - m)[..., None]
        glow = cv2.GaussianBlur(room * inv, (0, 0), w / 40) / np.maximum(cv2.GaussianBlur(1 - m, (0, 0), w / 40), 1e-3)[..., None]
        edge = np.clip(m * (1 - m) * 4, 0, 1)[..., None]
        person = person + self.wrap * edge * (glow - person)
        # 4) background defocus (mask-aware, so no halo around her)
        if self.bg_blur > 0:
            sig = self.bg_blur * w / 720
            room = cv2.GaussianBlur(room * inv, (0, 0), sig) / np.maximum(cv2.GaussianBlur(1 - m, (0, 0), sig), 1e-3)[..., None]
        out = m[..., None] * person + (1 - m[..., None]) * room
        out = np.clip(out, 0, 255).astype(np.uint8)
        La = lab(out); spa = stats(La, core)
        if spa: self.after.append((spa[0][0] - mr[0], spa[1] / max(1, cr)))
        return out

    def report(self):
        b = np.array(self.before) if self.before else np.zeros((1, 2)); a = np.array(self.after) if self.after else np.zeros((1, 2))
        return (f"person-vs-room brightness dL {b[:,0].mean():+.1f} -> {a[:,0].mean():+.1f}, "
                f"saturation ratio {b[:,1].mean():.2f} -> {a[:,1].mean():.2f}")


def run_video(src, dst, B):
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", str(dst)],
                          stdin=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    n = 0
    try:
        while True:
            ok, f = cap.read()
            if not ok: break
            ff.stdin.write(B.frame(f).tobytes()); n += 1
        ff.stdin.close(); ff.wait()
    except Exception:
        ff.kill(); raise          # never leave an orphan ffmpeg writing the output (3 Nov: two writers corrupted blended.mp4)
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--strength", type=float, default=0.4)
    ap.add_argument("--bg-blur", type=float, default=0.0, help="background defocus sigma at 720 px wide (close framings: 2-3)")
    ap.add_argument("--wrap", type=float, default=0.35)
    a = ap.parse_args()
    B = Blender(a.strength, a.bg_blur, a.wrap)
    if a.src.lower().endswith((".png", ".jpg", ".jpeg")):
        img = cv2.imread(a.src); cv2.imwrite(a.dst, B.frame(img)); print("still done |", B.report())
    else:
        n = run_video(a.src, a.dst, B); print(f"{n} frames | {B.report()}")
