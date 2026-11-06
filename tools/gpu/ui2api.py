"""Convert a ComfyUI UI-format workflow (what the browser saves) to API format (what /prompt takes), using the live /object_info."""
import json
CONN = lambda t: isinstance(t, str) and t.isupper() and t not in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")
SKIP = {"Reroute", "MarkdownNote", "Note", "PreviewImage"}

def convert(ui, info):
    nodes = {n["id"]: n for n in ui["nodes"]}
    links = {l[0]: (l[1], l[2]) for l in ui["links"]}
    def src(link_id):
        nid, slot = links[link_id]
        n = nodes[nid]
        while n["type"] == "Reroute":                      # follow reroutes back to the real output
            nid, slot = links[n["inputs"][0]["link"]]; n = nodes[nid]
        return [str(nid), slot]
    api = {}
    for n in ui["nodes"]:
        if n["type"] in SKIP or n.get("mode", 0) in (2, 4): continue
        spec = info[n["type"]]["input"]
        order = list(spec.get("required", {}).items()) + list(spec.get("optional", {}).items())
        linked = {i["name"]: src(i["link"]) for i in n.get("inputs", []) if i.get("link") is not None}
        wv = n.get("widgets_values")
        inputs = {}
        if isinstance(wv, dict):                           # VideoHelperSuite style: named widgets
            inputs.update({k: v for k, v in wv.items() if k in dict(order)})
        else:
            wv = list(wv or []); k = 0
            for name, t in order:
                typ = t[0]
                if CONN(typ) : continue
                if k < len(wv): inputs[name] = wv[k]
                k += 1
                opts = t[1] if len(t) > 1 and isinstance(t[1], dict) else {}
                if opts.get("control_after_generate") or (name in ("seed", "noise_seed") and typ == "INT"): k += 1   # skip "fixed/randomize"
        inputs.update(linked)
        api[str(n["id"])] = {"class_type": n["type"], "inputs": inputs}
    return api
