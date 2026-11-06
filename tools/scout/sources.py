"""Print the list of pages to sweep today: one line per page  ->  SRC_LABEL|URL"""
import json, pathlib
c = json.load(open(pathlib.Path(__file__).parent/"seeds.json"))
for name, aid in list(c["audios"].items()) + list(c["learned_audios"].items()):
    print(f"audio:{name.split(' - ')[0][:30]}|https://www.instagram.com/reels/audio/{aid}/")
for t in c["hashtags"]:
    print(f"tag:{t}|https://www.instagram.com/explore/search/keyword/?q=%23{t}")
