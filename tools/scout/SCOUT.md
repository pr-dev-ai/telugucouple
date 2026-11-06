---
name: padma-trend-scout
description: Daily trend scout for Padma (@satyam_padma.reels): find trending Telugu solo saree/half-saree dance reels (10K+ views) like Padma's Sakkani winner, gate them, and send numbered previews to Pradeep for approval.
---

# Padma trend scout

Finds today's best reference reels for Padma (@satyam_padma.reels, the couple app in `D:\telugucouple`) and saves them, already checked, into `D:\telugucouple\ready-to-create\<YYYY-MM-DD>\` (`NN_<song>_<code>.mp4`, `preview\NN_<song>.mp4`, `picks.md`, `picks.json`, `sheet.jpg`). Pradeep plays the numbered previews in the Claude app and replies with the numbers to make (2 reels a day, posted 6:00 PM and 9:30 PM IST).

It is a copy of the Siri trend scout. Differences: exemplars are frames of Padma's best reel (Sakkani Chinnodi Kosam, DfTRzQ7gqPG, 10K+ views); the fit prompt describes Padma (glamorous curvy young Telugu aunty, saree / half-saree, waist showing); any reel Siri's scout already picked (`D:\siri\ready-to-create\*\picks.json`) is skipped so the two accounts do not copy the same reels.

Needs: Pradeep's PC online (device bridge, VM shell at `$HOME/mnt/telugucouple`) and Claude in Chrome connected with Instagram logged in. Scripts live in `D:\telugucouple\tools\scout\` (VM path `$HOME/mnt/telugucouple/tools/scout`). A daily scheduled task "Padma trend scout" runs this in the morning.

## Rules
- Read only. Never like, follow, comment, save, post or DM during a scout. Never enter passwords; if Instagram shows a login or challenge page, stop and tell Pradeep.
- Any logged-in account in Chrome works for reading (satyam_padma.reels is fine). Do not switch accounts unless the page is logged out.
- Slow pace only (the scripts wait 0.45-0.85 s between API calls). If score.js reports http429, stop for the day and report.
- Skip the run if `ready-to-create/<today>/picks.md` already exists (just resend the previews).

## Setup per VM session (the VM forgets installs)
- `pip install --user -q mediapipe httpx yt-dlp insightface`
- libEGL for mediapipe: if `$HOME/libegl/root/usr/lib/x86_64-linux-gnu/libEGL.so.1` is missing: `mkdir -p ~/libegl && cd ~/libegl && apt-get download libegl1 libglvnd0 libgles2 libegl-mesa0 libgbm1 libwayland-server0 libwayland-client0 libxcb-randr0 libdrm2 && for d in *.deb; do dpkg -x $d root; done`

## Steps
1. Load Chrome tools in one ToolSearch call (tabs_context_mcp, tabs_create_mcp, navigate, javascript_tool, browser_batch, computer, tabs_close_mcp). Open a new tab on https://www.instagram.com/ and confirm it is logged in.
2. On the PC: `cd $HOME/mnt/telugucouple/tools/scout && python3 sources.py` -> one `LABEL|URL` line per page (seed audio pages + learned audios + 8 hashtags). `cat grab.js rows.js`.
3. In the tab: `sessionStorage.removeItem('__scoutCodes')`. For each source line: navigate to the URL, wait 4-5 s, run grab.js with `'SRC'` replaced by the label (keep the leading `await`). Batch several pages per browser_batch.
4. On the PC: `python3 cfg_score.py` prints score.js with the filters (10K+ views, 30 days or newer, 9-35 s, not own/paid/collab, not already seen) baked in. Paste it into the tab. Poll `await new Promise(r=>setTimeout(r,29000)); JSON.stringify(window.__scoutState)` until `done:true` (about 1.5 s per reel).
5. Run rows.js in the tab, then read `window.__rows.slice(i,i+8).join('\n')` in chunks of 8. Write all rows to `$HOME/mnt/telugucouple/ready-to-create/<date>/_work/rows.txt` with a heredoc, then `python3 rows2json.py <that _work dir>`.
6. `LD_LIBRARY_PATH=$HOME/libegl/root/usr/lib/x86_64-linux-gnu python3 scout.py run --date <date> --budget 145` repeatedly (each call under 180 s) until it prints DONE. Per candidate: yt-dlp download, `ref_check.py` (Gate 0: full body, one person, not dark/close-up), Claude vision fit check against Padma's exemplars.
7. `python3 scout.py final --date <date>`: ranks, max 2 per song, skips Siri's picks, copies the top 8, writes picks.md/picks.json/sheet.jpg and numbered phone previews in `preview\`, updates `seen.json` and `learned_audios`.
8. Delivery: stage every file in `preview\` plus `sheet.jpg` with device_stage_files, send them with SendUserFile (display render, status proactive) in pick order, with a caption listing each number, song, views and one line on why it fits. Ask Pradeep to reply with the 2 numbers to make today. Close the tab you opened.

## After Pradeep replies with numbers
Look up the numbers in `ready-to-create/<date>/picks.json` (file, code, best window) and make them through the gates in `D:\telugucouple\tools`:
1. `make_multishot.py submit <ref> --name <song>_solo --solo padma --route mc --start <best start> --dur <best dur> --cuts none --slot evening --stills-only` (the place comes from the reference reel, mirrored; sanity face gate + Claude realism judge with retries). Send the still to Pradeep.
2. Optional 3-second test: `test3s.py submit <reel_dir> t1 fal-ai/kling-video/v2.6/standard/motion-control <start>`.
3. On his OK: the same submit without `--stills-only` -> `poll.py` -> `make_multishot.py restore` -> `join` -> `finish.py --who padma --audio <ref> --offset <start>` (no blend pass: the place is the reference's own). Send post copy (~8 MB) for approval, then post at 6:00 PM / 9:30 PM with the AI label on.
Wardrobe: Indian wear only (no western dresses): silk or chiffon saree with a deep-neck blouse, or half-saree, waist showing; from `characters.choose_look("evening")`.
