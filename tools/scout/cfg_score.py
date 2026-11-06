"""Print score.js with today's filters + seen list baked in (paste the output into the Instagram tab)."""
import json, pathlib
H = pathlib.Path(__file__).parent; c = json.load(open(H/"seeds.json")); seen = json.load(open(H/"seen.json")) if (H/"seen.json").exists() else []
cfg = {k: c[k] for k in ("exclude_users", "min_views", "max_age_days", "min_dur", "max_dur")}; cfg["seen"] = seen
print((H/"score.js").read_text().replace("__CFG__", json.dumps(cfg)))
