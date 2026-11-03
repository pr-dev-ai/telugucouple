"""Gate + realism export (+ song) for a finished reel folder:
  python finish.py reels/<folder> [--who couple|satyam|padma] [--audio <ref.mp4> --offset <s>]
Source: blended.mp4 (after make_multishot blend) > joined.mp4 > merged/restored/motion/i2v.
Export: export_reel.sh (one shared grade, handheld drift, highlight glow, vignette, grain) so person and room read as ONE phone video.
With --audio: the reference song is muxed at --offset -> post.mp4 (what gets uploaded)."""
import pathlib, subprocess, sys
HERE = pathlib.Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
who = opt("--who", "couple")
d = pathlib.Path(args[0])
src = next(p for p in [d/"blended.mp4", d/"joined.mp4", d/"merged.mp4", d/"restored2.mp4", d/"restored.mp4", d/"motion.mp4", d/"i2v.mp4", d/"replace.mp4"] if p.exists())
print("source", src.name, "" if src.name == "blended.mp4" else "(WARNING: no blend pass; run make_multishot.py blend first)")
gate = subprocess.run([sys.executable, str(HERE/"face_gate.py"), "video", "--who", who, str(src)], capture_output=True, text=True)
print((gate.stdout.strip().splitlines() or [gate.stderr.strip()[-300:]])[-1])
final = d/"final.mp4"
r = subprocess.run(["bash", str(HERE/"export_reel.sh"), str(final), str(src)], capture_output=True, text=True)
print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")
if r.returncode != 0:
    sys.exit("export failed (black frames or ffmpeg error)")
print("final", final, "(gate", "PASS" if gate.returncode == 0 else "FAIL", ")")
if opt("--audio"):
    post = d/"post.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-ss", opt("--offset", "0"), "-i", opt("--audio"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(post)], check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(post)], capture_output=True, text=True).stdout.strip()
    print("post", post, f"{dur}s", f"{post.stat().st_size/1e6:.1f} MB")
