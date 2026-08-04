#!/bin/bash
set -e
S="Potato_Tomato_Boogie_final.mp3"
NORM="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"
ffmpeg -y -v error \
 -ss 0   -t 3.5 -i clip_fog_intro.mp4 \
 -ss 0.5 -t 3.0 -i clip_dj_build.mp4 \
 -ss 1.0 -t 2.5 -i clip_dj.mp4 \
 -ss 0.5 -t 3.0 -i clip_crowd_jump.mp4 \
 -ss 0.5 -t 2.0 -i clip_duo_floor.mp4 \
 -loop 1 -t 0.35 -i card_potato.png \
 -ss 1.0 -t 1.8 -i clip_potato_solo.mp4 \
 -loop 1 -t 0.35 -i card_tomato.png \
 -ss 1.0 -t 1.8 -i clip_tomato_bop.mp4 \
 -ss 0.5 -t 2.5 -i clip_crowd.mp4 \
 -ss 0.5 -t 3.0 -i clip_duo_spin.mp4 \
 -ss 0.5 -t 2.5 -i clip_kitchen.mp4 \
 -ss 0.5 -t 3.0 -i clip_finale.mp4 \
 -ss 51 -t 33 -i "$S" \
 -filter_complex "[0:v]${NORM}[v0];[1:v]${NORM}[v1];[2:v]${NORM}[v2];[3:v]${NORM}[v3];[4:v]${NORM}[v4];[5:v]${NORM}[v5];[6:v]${NORM}[v6];[7:v]${NORM}[v7];[8:v]${NORM}[v8];[9:v]${NORM}[v9];[10:v]${NORM}[v10];[11:v]${NORM}[v11];[12:v]${NORM}[v12];[v0][v1][v2][v3][v4][v5][v6][v7][v8][v9][v10][v11][v12]concat=n=13:v=1:a=0[v]" \
 -map "[v]" -map 13:a:0 -c:v libx264 -profile:v high -crf 21 -preset medium -c:a aac -b:a 192k -shortest -movflags +faststart \
 Potato_Tomato_Boogie_TECHNO_draft1_1080p_9x16.mp4
