# KAZ AI Video Factory V4

CPU-compatible automated video **draft** pipeline on GitHub Actions. Outputs MP4 with burned-in Vietnamese text subtitles, cover PNG, separate SRT, scripts, schedule CSV and manifest JSON. Optional online edge-tts Vietnamese narration. Uses supplied licensed photos in `kaz-factory/assets/video_001.png`, otherwise a generated graphic placeholder. It does not generate AI images or AI-researched scripts, and does not upload or publish to social platforms.

## How to use
Actions -> KAZ Factory V4 -> Run workflow -> enter count 1 and voice none (first test). Wait for the build; download the `kaz-video-drafts-*` artifact, retained 7 days. The scheduled daily workflow creates one test draft until you change its scheduled count; 50/day is not guaranteed. You can run locally with `python kaz-factory/factory.py --count 1 --duration 40 --burn-subs`.

For online Vietnamese voice, select voice=edge. This free unofficial remote TTS can fail or rate-limit, and a too-long narration aborts the job rather than cutting it silently. Subtitles are estimated sentence segments, not accurate word alignment. Change topics in topics/topics.txt. Content is an unverified template, not verified educational commentary.

## Limitations
Workflow on the default branch is required for scheduling. GitHub Actions is not an on-demand GPU service. Generated videos are **review-required drafts**, not ready to automatically post; official TikTok/YouTube/Facebook publishing needs approved credentials/permissions. Never put private keys or tokens into repository files. Do not publish repetitive or misleading content.
