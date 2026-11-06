#!/bin/bash
# Pod start command: run ComfyUI from the network volume.
cd /workspace/ComfyUI && . /workspace/venv/bin/activate && exec python main.py --listen 0.0.0.0 --port 8188
