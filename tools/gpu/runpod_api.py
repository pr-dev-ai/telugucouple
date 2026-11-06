"""Minimal RunPod REST client (pods). Key: RUNPOD_API_KEY in D:\\siri\\.env"""
import json, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]
def key():
    for l in (ROOT / ".env").read_text().splitlines():
        if l.startswith("RUNPOD_API_KEY="): return l.split("=", 1)[1].strip()
    raise SystemExit("add RUNPOD_API_KEY=... to D:\\siri\\.env")
def call(method, path, body=None):
    r = urllib.request.Request(f"https://rest.runpod.io/v1{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            t = resp.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e: return {"http": e.code, "body": e.read().decode()[:400]}
def create_pod(cfg, start_cmd):
    body = {"name": "studio-scail2", "imageName": cfg["image"], "gpuTypeIds": cfg["gpu_types"], "gpuCount": 1, "cloudType": cfg.get("cloud", "SECURE"),
            "networkVolumeId": cfg["volume_id"], "containerDiskInGb": 30, "ports": ["8188/http", "22/tcp"],
            "dockerStartCmd": ["bash", "-c", start_cmd], "interruptible": cfg.get("spot", False)}
    if cfg.get("datacenter"): body["dataCenterIds"] = [cfg["datacenter"]]
    return call("POST", "/pods", body)
def get_pod(pid): return call("GET", f"/pods/{pid}")
def delete_pod(pid): return call("DELETE", f"/pods/{pid}")
def create_volume(name, gb, datacenter): return call("POST", "/networkvolumes", {"name": name, "size": gb, "dataCenterId": datacenter})
def proxy(pid, port=8188): return f"https://{pid}-{port}.proxy.runpod.net"
