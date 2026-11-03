#!/usr/bin/env bash
# Realism export (v2): joins shot clips and makes them look like one handheld phone video.
#   export_reel.sh out.mp4 shot1.mp4 [shot2.mp4 ...]
# handheld drift + highlight glow + one shared grade + vignette + grain; 1080x1920, 30 fps, no audio, < 30 MB.
set -e; out=$1; shift; n=$#; ins=""; fc=""; cat=""; i=0
for f in "$@"; do ins="$ins -i $f"; fc="$fc[$i:v]scale=1080:1920:flags=lanczos,fps=30,setsar=1[v$i];"; cat="$cat[v$i]"; i=$((i+1)); done
ffmpeg -v error -y $ins -filter_complex "${fc}${cat}concat=n=$n:v=1[c];\
[c]scale=1188:2112,crop=1080:1920:'(iw-ow)/2+14*sin(2*PI*t*0.37)+7*sin(2*PI*t*1.13)+2*sin(2*PI*t*4.1)':'(ih-oh)/2+12*sin(2*PI*t*0.29+1)+6*sin(2*PI*t*0.97)+2*sin(2*PI*t*3.7)',\
eq=contrast=0.94:saturation=0.93:gamma=1.02,colorbalance=rs=0.03:bs=-0.03:rm=0.02:bh=-0.02,split[m][h];\
[h]curves=all='0/0 0.72/0 1/1',gblur=sigma=22[bl];[m][bl]blend=all_mode=screen:all_opacity=0.35,\
vignette=PI/5,gblur=sigma=0.6,noise=alls=7:allf=t,unsharp=3:3:0.2[o]" -map "[o]" -an \
  -c:v libx264 -preset medium -crf 23 -maxrate 10M -bufsize 15M -pix_fmt yuv420p -movflags +faststart "$out"
ffmpeg -i "$out" -vf blackdetect=d=0.1:pic_th=0.90:pix_th=0.10 -an -f null - 2>&1 | grep -o 'black_start[^ ]*' && { echo "BLACK FRAMES - reject"; exit 3; } || echo "ok, no black frames"
