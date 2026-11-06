"""rows.txt (pipe rows from score.js window.__rows) -> candidates.json.  python rows2json.py <day>/_work"""
import sys, json, pathlib
w = pathlib.Path(sys.argv[1]); out = []
for l in (w/"rows.txt").read_text(encoding="utf-8").splitlines():
    p = l.strip().split("|")
    if len(p) < 11: continue
    out.append(dict(code=p[0], url=f"https://www.instagram.com/reel/{p[0]}/", user=p[1], views=int(p[2]), likes=int(p[3]), age_days=float(p[4]),
                    vpd=int(p[5]), dur=float(p[6]), audio_type="licensed_music" if p[7] == "L" else "original_sounds", song=p[8], artist="", audio_id=p[9], srcs=p[10].split("+")))
json.dump(out, open(w/"candidates.json", "w"), indent=1, ensure_ascii=False); print(len(out), "candidates")
