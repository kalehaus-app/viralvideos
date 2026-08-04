# "Mommy Mommy, I Can't Sleep!" — Happy Tots 30s Short

AI-generated 30-second vertical (9:16) YouTube Short for a toddler bedtime
nursery-rhyme show. Baby can't sleep because of scary monster shadows; Mommy
comforts Baby with a gentle lullaby and hugs until Baby falls peacefully asleep.

## Files
- `Mommy_I_Cant_Sleep_HappyTots_30s_Shorts.mp4` — final 30s deliverable (720x1280, with audio)
- `v_scene1.png` / `v_scene2.png` — vertical keyframes used as start frames
- `clip1.mp4` / `clip2.mp4` — the two 15s source clips (scene 1 + scene 2)

## Pipeline
1. Keyframes: nano-banana (9:16, consistent cartoon style)
2. Animation: Kling 3.0 image-to-video, 15s each, native audio (sound=on)
3. Stitch: ffmpeg concat -> 720x1280, H.264, AAC, 30 fps
