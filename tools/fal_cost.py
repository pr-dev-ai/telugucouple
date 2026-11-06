"""Cost log for every paid call. Prices are fal list (USD) as of 1 Nov 2026; edit when they change.
Every generator calls spend(endpoint, units) after a successful call; the log is out/spend.csv.
  python fal_cost.py            # monthly totals
"""
import csv, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "out" / "spend.csv"
USD_INR = 88
# unit = image, or second of output video (Kling MC bills on the REFERENCE clip length; Wan Animate bills frames/16)
PRICES = {
    "google/nano-banana-2.1/edit":                       ("image", 0.054),   # MEASURED on fal dashboard 3 Nov 2026 ($6.65/123 calls); fal bills every input image (~$0.002 each)
    "fal-ai/nano-banana-2/edit":                         ("image", 0.080),   # superseded, kept for reference
    "fal-ai/nano-banana-pro/edit":                       ("image", 0.150),
    "fal-ai/nano-banana-pro":                            ("image", 0.150),
    "fal-ai/kling-video/v2.6/standard/motion-control":   ("second", 0.070),
    "fal-ai/kling-video/v3/standard/motion-control":     ("second", 0.126),
    "fal-ai/kling-video/v3/pro/motion-control":          ("second", 0.168),
    "fal-ai/wan/v2.2-14b/animate/replace":               ("second", 0.080),  # 720p; 580p 0.06; 480p 0.04 (see spend(..., res=))
    "fal-ai/kling-video/v2.5-turbo/pro/image-to-video":  ("second", 0.070),
    "fal-ai/flux-lora-fast-training":                    ("run", 2.000),
    "fal-ai/wan/v2.2-14b/animate/move":                  ("second", 0.080),  # same tiers as replace
    "wavespeed-ai/wan-2.2/animate-2":                    ("second", 0.040),  # WaveSpeed 480p (720p 0.08), whole seconds of driving video
    "wavespeed-ai/scail-2":                              ("second", 0.040),  # WaveSpeed 480p (720p 0.08)
    "wavespeed-ai/steadydancer":                         ("second", 0.040),  # WaveSpeed 480p (720p 0.08)
    "fal-ai/bytedance/omnihuman/v1.5":                  ("second", 0.160),  # fal list 4 Nov 2026 (billed on audio length)
    "fal-ai/sync-lipsync/v2/pro":                        ("second", 0.0833), # $5/min, fal list 4 Nov 2026
    "bytedance/dreamactor-v2":                           ("second", 0.050),  # WaveSpeed, any resolution, max 30 s
}
WAN_RES = {"480p": 0.04, "580p": 0.06, "720p": 0.08}

def refund(endpoint, units, note=""):
    """fal does not bill server-side failures (5xx: generation_timeout, downstream_service_unavailable). Log the reversal
    so spend.csv matches the fal usage page (3 Nov 2026: 606 s submitted, 429 s billed)."""
    return spend(endpoint, -abs(units), "REFUND " + note)

def spend(endpoint, units, note="", res=None):
    kind, price = PRICES.get(endpoint, ("?", 0.0))
    if endpoint.startswith("fal-ai/wan/") and res in WAN_RES:
        price = WAN_RES[res]
    usd = round(units * price, 4)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["date", "endpoint", "units", "unit", "usd", "inr", "note"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), endpoint, units, kind, usd, round(usd * USD_INR, 1), note])
    return usd

if __name__ == "__main__":
    if not LOG.exists(): sys.exit("no spend yet")
    tot = {}
    for r in csv.DictReader(open(LOG)):
        m = r["date"][:7]; tot[m] = tot.get(m, 0) + float(r["usd"])
    for m, v in sorted(tot.items()): print(m, f"${v:.2f}", f"₹{v*USD_INR:.0f}")

# --- Claude API cost (judge, scout), added 5 Nov 2026. List prices per million tokens (platform.claude.com pricing page).
CLAUDE_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
def log_claude(resp_json, note=""):
    try:
        u = resp_json.get("usage") or {}; m = resp_json.get("model", "claude-opus-5-5")
        pin, pout = next((v for k, v in CLAUDE_PRICES.items() if m.startswith(k)), (4.0, 20.0))
        tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        usd = round(tin / 1e6 * pin + u.get("output_tokens", 0) / 1e6 * pout, 4)
        LOG.parent.mkdir(parents=True, exist_ok=True); new = not LOG.exists()
        with LOG.open("a", newline="") as f:
            w = csv.writer(f)
            if new: w.writerow(["date", "endpoint", "units", "unit", "usd", "inr", "note"])
            w.writerow([time.strftime("%Y-%m-%d %H:%M"), f"anthropic/{m}", tin + u.get("output_tokens", 0), "token", usd, round(usd * USD_INR, 1), note])
        return usd
    except Exception as ex:
        print("claude cost log skipped:", ex); return 0.0
