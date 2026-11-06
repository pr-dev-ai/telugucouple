#!/bin/bash
# Runs ON the rented GPU pod, once, to fill the network volume (/workspace). Idempotent: re-running only fills gaps.
set -e
cd /workspace
[ -d ComfyUI ] || git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git
[ -d venv ] || python3 -m venv venv
. venv/bin/activate
pip install -q --upgrade pip
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -q -r ComfyUI/requirements.txt huggingface_hub[hf_transfer]
cd ComfyUI/custom_nodes
[ -d ComfyUI-VideoHelperSuite ] || git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
[ -d ComfyUI-Frame-Interpolation ] || git clone --depth 1 https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git
pip install -q -r ComfyUI-VideoHelperSuite/requirements.txt || true
(cd ComfyUI-Frame-Interpolation && python install.py) || true
cd /workspace/ComfyUI/models
export HF_HUB_ENABLE_HF_TRANSFER=1
dl() { [ -f "$2/$(basename $3)" ] || huggingface-cli download "$1" "$3" --local-dir "/workspace/_hf/$1" && mkdir -p "$2" && ln -sf "/workspace/_hf/$1/$3" "$2/$(basename $3)"; }
dl Comfy-Org/SCAIL-2 diffusion_models diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors
dl Comfy-Org/Wan_2.1_ComfyUI_repackaged text_encoders split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
dl Comfy-Org/Wan_2.1_ComfyUI_repackaged clip_vision split_files/clip_vision/clip_vision_h.safetensors
dl Comfy-Org/Wan_2.1_ComfyUI_repackaged vae split_files/vae/wan_2.1_vae.safetensors
dl Comfy-Org/sam3.1 checkpoints checkpoints/sam3.1_multiplex_fp16.safetensors
dl lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v loras loras/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors
du -sh /workspace/_hf; echo SETUP_DONE
