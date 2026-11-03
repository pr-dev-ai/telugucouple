"""Gate + export a finished reel folder: python finish.py reels/<folder> [--who couple|satyam|padma]
Expects joined.mp4 (from make_multishot join) or restored*.mp4 / merged.mp4 / motion.mp4 / i2v.mp4 / replace.mp4."""
import pathlib, subprocess, sys
HERE = pathlib.Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
who = sys.argv[sys.argv.index("--who") + 1] if "--who" in sys.argv else "couple"
d = pathlib.Path(args[0])
src = next(p for p in [d/"joined.mp4", d/"merged.mp4", d/"restored2.mp4", d/"restored.mp4", d/"motion.mp4", d/"i2v.mp4", d/"replace.mp4"] if p.exists())
gate = subprocess.run([sys.executable, str(HERE/"face_gate.py"), "video", "--who", who, str(src)], capture_output=True, text=True)
print((gate.stdout.strip().splitlines() or [gate.stderr.strip()[-300:]])[-1])
final = d/"final.mp4"
subprocess.run(["ffmpeg","-v","error","-y","-i",str(src),
  "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "noise=alls=5:allf=t,unsharp=5:5:0.35,fps=30",  # phone-camera grain; Instagram's own AI label covers disclosure
  "-an","-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(final)], check=True)
print("final", final, "(gate", "PASS" if gate.returncode==0 else "FAIL", ")")

# Black-frame check: any black stretch over 0.1 s fails the reel (FaceFusion temp clashes have produced black tails)
bd = subprocess.run(["ffmpeg","-i",str(final),"-vf","blackdetect=d=0.1:pic_th=0.90:pix_th=0.10","-an","-f","null","-"],capture_output=True,text=True).stderr
bl = [l[l.find("black_start"):] for l in bd.splitlines() if "black_start" in l]
print("BLACK FRAMES:", bl if bl else "none")
if bl: sys.exit(3)
