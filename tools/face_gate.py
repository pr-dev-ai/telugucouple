"""
Face gate: is this Satyam? is this Padma? are BOTH in the frame? A number, not an opinion. Runs on the RTX 3050 (or CPU), no API cost.

  pip install insightface onnxruntime-gpu opencv-python numpy      (onnxruntime if no GPU)

  python face_gate.py init --who satyam                  # canonical embedding from identity/satyam/v1 (head shots s01-s07, averaged)
  python face_gate.py check --who padma img1.png dir/    # single-person images: score each; exit 1 if any fails
  python face_gate.py check --who couple still.png       # two-person images: both faces must match, exactly 2 subjects
  python face_gate.py video --who couple clip.mp4        # every 6th frame; PASS if each person's median >= 0.60 and <=20% of their frames < 0.45
  python face_gate.py calibrate --who satyam             # scores the sheet against itself and suggests a threshold

Scores are cosine similarity of ArcFace embeddings (buffalo_l). Same person is usually 0.55 to 0.8, different people under 0.3.
Every check appends a line to out/face_gate.log so each reel has its scores on record.
"""
import argparse, itertools, pathlib, sys, time

import cv2
import numpy as np

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import characters as ch

LOG = ROOT / "out" / "face_gate.log"
THRESHOLD = 0.60   # median of clear frames (video) or the image score
FLOOR = 0.45       # at most 20% of a person's clear video frames may fall below this (turns, hair across the face)
VIDEO_STRIDE = 6
VIDEO_MIN_FACE_PX = 30   # wide dance shots at 720p have ~40 px faces; FaceFusion restores them, so judge them
MIN_FACE_PX = 48         # faces narrower than this (far background people, 480p wides) are not judged
SECOND_SUBJECT = 0.6     # another face counts as a subject only if its width is >= 60% of the main face
SMALL_FACE_PX = 110      # below this width the ArcFace crop is blurry: re-embed from an upscaled crop and use THRESHOLD_SMALL
THRESHOLD_SMALL = 0.55
UPSCALE = 3

_app = None
_canon = {}


def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app


def canonical(who):
    if who not in _canon:
        p = ch.ident(who) / "canonical_embedding.npy"
        if not p.exists():
            sys.exit(f"run: python face_gate.py init --who {who}")
        _canon[who] = np.load(p)
    return _canon[who]


def _norm(e):
    return e / np.linalg.norm(e)


def _upscaled_embed(img_bgr, f):
    """Crop the face with margin, upscale it, re-detect, and return the (sharper) embedding, or None."""
    h, w = img_bgr.shape[:2]
    x0, y0, x1, y1 = f.bbox
    fw, fh = x1 - x0, y1 - y0
    X0, Y0 = int(max(0, x0 - fw)), int(max(0, y0 - fh))
    X1, Y1 = int(min(w, x1 + fw)), int(min(h, y1 + fh))
    crop = img_bgr[Y0:Y1, X0:X1]
    if crop.size == 0:
        return None
    big = cv2.resize(crop, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_LANCZOS4)
    faces = app().get(big)
    if not faces:
        return None
    g = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    return _norm(g.normed_embedding)


def faces_of(img_bgr, min_px=None):
    """All subject faces in the image, largest first: list of (embedding, width_px, insightface_face). Faces that are tiny next
    to the largest one (background people) are dropped, same rule as before."""
    fs = app().get(img_bgr)
    fs = [f for f in fs if (f.bbox[2] - f.bbox[0]) >= (min_px or MIN_FACE_PX)]
    if not fs:
        return []
    fs.sort(key=lambda x: -(x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    main_w = fs[0].bbox[2] - fs[0].bbox[0]
    out = []
    for f in fs:
        w = f.bbox[2] - f.bbox[0]
        if f is not fs[0] and w < SECOND_SUBJECT * main_w:
            continue
        e = _norm(f.normed_embedding)
        if w < SMALL_FACE_PX:
            e2 = _upscaled_embed(img_bgr, f)
            if e2 is not None:
                e = e2
        out.append((e, float(w), f))
    return out


MIN_OVERRIDE = None     # --min X: one threshold for every face (sanity check of a raw couple still before FaceFusion fixes the faces)


def thr_for(w):
    if MIN_OVERRIDE is not None:
        return MIN_OVERRIDE
    return THRESHOLD_SMALL if w < SMALL_FACE_PX else THRESHOLD


def score_single(img_bgr, who, min_px=None):
    """(score, n_subjects, face_width) for one-person images/frames: the largest face against <who>."""
    fs = faces_of(img_bgr, min_px)
    if not fs:
        return None, 0, 0
    e, w, _ = fs[0]
    return float(np.dot(e, canonical(who))), len(fs), w


def score_couple(img_bgr, min_px=None):
    """{who: (score, width)} for two-person images/frames. Each character gets the face that fits it best (assignment with the
    highest total similarity), no face is used twice. Returns also n_subjects. Faces missing -> that character is absent."""
    fs = faces_of(img_bgr, min_px)
    whos = ch.WHO
    if not fs:
        return {}, 0
    best, best_sum = None, -9
    for perm in itertools.permutations(range(len(fs)), min(len(fs), len(whos))):
        s = 0.0; asg = {}
        for who, fi in zip(whos, perm):
            v = float(np.dot(fs[fi][0], canonical(who))); s += v; asg[who] = (v, fs[fi][1])
        if s > best_sum:
            best, best_sum = asg, s
    return best, len(fs)


def log(kind, name, s, ok, extra=""):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{kind}\t{name}\t{s}\t{'PASS' if ok else 'FAIL'}\t{extra}\n")


def init(who):
    ident = ch.ident(who)
    heads = sorted(ident.glob("s0[1-7]*.png"))  # head shots only, not full body
    embs = []
    for p in heads:
        fs = faces_of(cv2.imread(str(p)))
        if fs:
            embs.append(fs[0][0]); print("ok", p.name)
        else:
            print("no face", p.name)
    if not embs:
        sys.exit(f"no faces found in {ident}")
    c = _norm(np.mean(embs, axis=0))
    np.save(ident / "canonical_embedding.npy", c)
    print(f"{who}: canonical embedding from {len(embs)} images saved to {ident / 'canonical_embedding.npy'}")


def _files(paths):
    files = []
    for p in map(pathlib.Path, paths):
        files += sorted(p.glob("*.png")) + sorted(p.glob("*.jpg")) if p.is_dir() else [p]
    return files


def check(who, paths):
    failed = 0
    for p in _files(paths):
        img = cv2.imread(str(p))
        if who == "couple":
            asg, n = score_couple(img)
            parts, ok = [], n == 2 and len(asg) == 2
            for w_ in ch.WHO:
                if w_ in asg:
                    v, fw = asg[w_]; good = v >= thr_for(fw); ok = ok and good
                    parts.append(f"{w_} {v:.3f}{'' if good else '!'} ({int(fw)}px)")
                else:
                    parts.append(f"{w_} missing"); ok = False
            why = "" if ok else (f"{n} subjects" if n != 2 else "drift")
            line = "  ".join(parts)
            print(f"{'PASS' if ok else 'FAIL'}  {line}  {p.name}  {why}")
            log("couple", p.name, line, ok, why)
        else:
            s, n, fw = score_single(img, who)
            thr = thr_for(fw) if fw else THRESHOLD
            ok = s is not None and s >= thr and n == 1
            why = "" if ok else ("no clear face" if s is None else (f"{n} subjects" if n != 1 else "drift"))
            print(f"{'PASS' if ok else 'FAIL'}  {s if s is None else round(s, 3)}  {p.name}  {why}  (face {int(fw)}px, thr {thr})")
            log(who, p.name, None if s is None else round(s, 3), ok, f"{why} face{int(fw)}px thr{thr}")
        failed += not ok
    sys.exit(1 if failed else 0)


def video(who, path):
    cap = cv2.VideoCapture(str(path))
    per = {w_: [] for w_ in (ch.WHO if who == "couple" else [who])}
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if i % VIDEO_STRIDE == 0:
            if who == "couple":
                asg, n = score_couple(frame, VIDEO_MIN_FACE_PX)
                for w_, (v, _) in asg.items():
                    per[w_].append(v)
            else:
                s, n, _ = score_single(frame, who, VIDEO_MIN_FACE_PX)
                if s is not None:
                    per[who].append(s)
        i += 1
    name = pathlib.Path(path).name
    ok_all, parts = True, []
    for w_, scores in per.items():
        if len(scores) < 6:
            ok_all = False; parts.append(f"{w_}: too few clear frames ({len(scores)})"); continue
        mn, med = min(scores), float(np.median(scores))
        low = sum(1 for s in scores if s < FLOOR) / len(scores)
        ok = med >= THRESHOLD and low <= 0.20
        ok_all = ok_all and ok
        parts.append(f"{w_}: median {med:.3f} min {mn:.3f} below-floor {low:.0%} frames {len(scores)}{'' if ok else ' FAIL'}")
    line = " | ".join(parts)
    print(f"{'PASS' if ok_all else 'FAIL'}  {line}  {path}")
    log("video", name, line, ok_all, who)
    sys.exit(0 if ok_all else 1)


def calibrate(who):
    c = canonical(who)
    vals = []
    for p in sorted(ch.ident(who).glob("s*.png")):
        fs = faces_of(cv2.imread(str(p)))
        if fs:
            vals.append((p.name, float(np.dot(fs[0][0], c))))
    for name, v in vals:
        print(f"{v:.3f}  {name}")
    lo = min(v for _, v in vals)
    print(f"\n{who}: lowest sheet score {lo:.3f}. Suggested THRESHOLD: {max(0.45, round(lo - 0.08, 2))}")
    print("Full-body images score lower because the face is small; that is expected.")
    # cross-check: the other character must score LOW against this canonical, or the two faces are too alike
    for other in ch.WHO:
        if other == who:
            continue
        oc = ch.ident(other) / "canonical_embedding.npy"
        if oc.exists():
            print(f"{other} canonical vs {who} canonical: {float(np.dot(np.load(oc), c)):.3f}  (want < 0.30)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "check", "video", "calibrate"])
    ap.add_argument("--who", required=True, choices=ch.WHO + ["couple"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min", type=float, help="check: use this one threshold for every face (sanity gate before the FaceFusion still fix)")
    a = ap.parse_intermixed_args()      # allows: check --who couple a.png b.png
    MIN_OVERRIDE = a.min
    if a.cmd == "init":
        init(a.who)
    elif a.cmd == "check":
        check(a.who, a.paths)
    elif a.cmd == "video":
        video(a.who, a.paths[0])
    else:
        calibrate(a.who)
