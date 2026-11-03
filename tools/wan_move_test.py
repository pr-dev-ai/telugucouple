"""Wan 2.2 Animate MOVE mode (fal, 480p, 16 fps reference) on one still + reference. Usage: python wan_move_test.py <dir> [submit|poll]"""
import sys, os, json, pathlib, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import make_candidates as mc, fal_cost
d = pathlib.Path(sys.argv[1]); cmd = sys.argv[2] if len(sys.argv) > 2 else "submit"
EP = "fal-ai/wan/v2.2-14b/animate/move"; rq = d / "wanmove_request.json"
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
if cmd == "submit":
    if rq.exists(): sys.exit("already submitted: " + rq.read_text())
    h = fal_client.submit(EP, arguments={"video_url": fal_client.upload_file(str(d / "ref16.mp4")), "image_url": fal_client.upload_file(str(d / "still.png")), "resolution": "480p"})
    secs = 15.1 * 16 / 16; fal_cost.spend(EP, round(secs, 2), "bakeoff_nadakallo wan-move", res="480p")
    rq.write_text(json.dumps({"id": h.request_id})); print("submitted", h.request_id)
else:
    rid = json.loads(rq.read_text())["id"]
    try:
        st = type(fal_client.status(EP, rid, with_logs=False)).__name__
        if st == "Completed":
            r = fal_client.result(EP, rid); urllib.request.urlretrieve(r["video"]["url"], d / "wanmove_480p.mp4"); print("saved", d / "wanmove_480p.mp4")
        else: print(st)
    except Exception as e:
        m = str(e); print("FAILED", m[:300]); fal_cost.refund(EP, 15.1, "bakeoff wan-move")
