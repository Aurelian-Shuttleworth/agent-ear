"""Video preprocessing module — YouTube download and local video handling.

Handles:
  - YouTube URL detection and yt-dlp download
  - Format selection optimised for Gemini multimodal analysis (720p max)
  - Local video passthrough
"""

import os
import re
import subprocess
import tempfile

# YouTube URL detection
YOUTUBE_PATTERN = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+")


def preprocess_video(video_path: str) -> str:
    """Download YouTube or passthrough local video.

    Args:
        video_path: Local file path or YouTube URL.

    Returns:
        Path to a local video file ready for upload.
    """
    if YOUTUBE_PATTERN.match(video_path):
        return download_youtube(video_path)
    return video_path


def download_youtube(url: str) -> str:
    """Download a YouTube video to a temporary file.

    Format selection optimised for Gemini multimodal analysis:
    - 720p max: Gemini samples video at 1 fps, so higher resolution is wasted
      bandwidth and risks exceeding the 20MB inline upload threshold.
    - MP4 container with merged audio: required for Gemini's audio+video analysis.
    - Falls back to best available MP4 if 720p isn't available.

    Returns:
        Path to temporary MP4 file.
    """
    print(f"⬇️  Downloading video from {url}...")
    tf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    temp_path = tf.name
    tf.close()

    import shutil

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("⚠️  ffmpeg not found on PATH — HLS/DASH streams may produce corrupted video")
        print("   Install ffmpeg or ensure it is on PATH for reliable video downloads")

    try:
        cmd = [
            "yt-dlp",
            # Prefer ≤720p mp4 with audio; fall back to best mp4 with separate audio merge
            "-f",
            "best[height<=720][ext=mp4]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "--merge-output-format",
            "mp4",
            "--no-playlist",
            "--force-overwrites",  # tempfile pre-creates a 0-byte file; must overwrite
            "-o",
            temp_path,
            url,
        ]
        # Explicitly tell yt-dlp where ffmpeg lives (wrapper PATH may not propagate)
        if ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            cmd.insert(1, "--ffmpeg-location")
            cmd.insert(2, ffmpeg_dir)

        subprocess.run(cmd, check=True)
        size_mb = os.path.getsize(temp_path) / (1024 * 1024)
        print(f"✅ Download complete: {temp_path} ({size_mb:.1f} MB)")
        if size_mb > 100:
            print("⚠️  File exceeds 100 MB inline limit — will use GCS or Files API")
        return temp_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"Video download failed: {e}")
