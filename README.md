# Satyam & Padma

Telugu AI couple on Instagram: a plain bald uncle and his beautiful glamorous wife dancing to trending reels inside their neat 3BHK in Kukatpally.
Cloned from the Siri app (D:\siri, github.com/pr-dev-ai/siri) on 3 Nov 2026 and changed for TWO people. See `identity/couple_bible.md`.

- `identity/characters.json`  the two characters and their reference images; `identity/<who>/v1` frozen face + body sheets (never regenerate)
- `tools/characters.py`      every face / body / clothes / room text used in prompts
- `sets/`                     the flat: one plate per room/angle, generated once (`make_sets.py`), passed into every still
- `refs/trends/<date>/`       trending couple-dance reels pulled with yt-dlp from the saved collection
- `reels/<date>_<name>/`      one folder per reel (ref, frames, stills, motion, restored, merged, joined, final)
- `jobs/`                     GPU worker queue (face restore in two passes, adb push, emulator)
- `out/`                      generated, gitignored (candidates, sheets, spend.csv, face_gate.log)

## One reel
```
python tools/make_multishot.py submit refs/trends/<date>/<ref>.mp4 --name <name> --start 0 --dur 15 --set hall_a --look "she in a red saree, he in banian and lungi" --route <mc|split|i2v>
python tools/poll.py reels/<date>_<name>
python tools/make_multishot.py restore reels/<date>_<name>      # worker.bat must be running on the PC
python tools/make_multishot.py join reels/<date>_<name>
python tools/finish.py reels/<date>_<name>                       # gate on both faces + final.mp4 + black-frame check
```
Then mux the reference audio at the right offset, push with an `adb_push` job and post from the emulator (Siri posting playbook).

## Rules
- Only ONE GPU worker runs at a time (this one or Siri's): both use the RTX 3050.
- Every still passes `face_gate.py check --who couple` (both faces, exactly 2 subjects) before any Kling money is spent.
- Padma's glamour stays in the saree register; full-body dance framing; AI label on every post.
