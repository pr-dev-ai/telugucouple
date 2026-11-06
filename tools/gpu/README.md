# SCAIL-2 on a rented GPU (built 5 Nov 2026)

Flow: `make_multishot.py submit ... --engine scail2gpu` makes the still as usual and drops a job in `D:\siri\gpu_queue\`.
Once a day `python tools/gpu/run_batch.py run` starts one RunPod pod, renders every queued job with the official SCAIL-2
ComfyUI workflow (context windows for >81 frames, 720p, RIFE 16->32 fps), downloads each clip as `motion_sXX.mp4`
into the reel folder, then DELETES the pod. `poll.py` sees the file and the normal restore -> brow_fix -> export steps continue.

Spend guards: pod deleted in `finally`; `max_hours_per_batch` (3 h) and `max_usd_per_day` ($4) in gpu_config.json; every
batch is logged to out/spend.csv as `runpod/<gpu>` with hours and $.

## One-time setup
1. Pradeep: create a RunPod account, add $10 credit, create an API key (read/write) and add `RUNPOD_API_KEY=...` to D:\siri\.env.
2. `python run_batch.py init <datacenter>` creates the 60 GB network volume (~Rs 370/month) in a data center that has 5090/4090.
3. `python run_batch.py setup` installs ComfyUI + VideoHelperSuite + Frame-Interpolation and downloads the models
   (SCAIL-2 fp8 17.7 GB, UMT5 fp8 6.7 GB, clip_vision_h, Wan VAE, SAM 3.1, lightx2v LoRA) onto the volume. ~20-30 min, ~$0.5.
4. First real run: 1 clip, measure minutes per clip, compare against DreamActor before switching any reels.

## Not yet verified (fix on first run)
- Exact HF file paths in setup_volume.sh (SAM 3.1, lightx2v LoRA) and the pod image tag.
- ui2api.py widget mapping against the live /object_info (it aborts with the missing node list if a node pack is absent).
- Timing per clip: estimates are 480p ~5 min / 720p ~10-12 min per 15 s clip on a 5090.
