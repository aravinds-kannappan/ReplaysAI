"""
Downloads a YouTube video via yt-dlp and extracts frames using OpenCV.
Returns base64-encoded JPEG frames for Claude Vision inference.
"""
import base64
import os
import subprocess
import tempfile
from typing import Optional
import cv2


def download_video(youtube_url: str, output_dir: str, max_seconds: int = 180) -> Optional[str]:
    """Download video to output_dir, return local file path."""
    output_path = os.path.join(output_dir, "highlight.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=480][ext=mp4]/best[height<=480]",
        "--output", output_path,
        "--no-playlist",
        "--no-audio",
        "--max-downloads", "1",
        youtube_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[yt-dlp] Error: {result.stderr[:300]}")
            return None
        for f in os.listdir(output_dir):
            if f.startswith("highlight"):
                return os.path.join(output_dir, f)
    except subprocess.TimeoutExpired:
        print("[yt-dlp] Download timed out")
    except Exception as e:
        print(f"[yt-dlp] Exception: {e}")
    return None


def extract_frames(video_path: str, interval_seconds: float = 2.0, max_frames: int = 60) -> list[str]:
    """Extract frames at interval_seconds, return list of base64-encoded JPEG strings."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = int(fps * interval_seconds)
    frames_b64: list[str] = []
    frame_idx = 0

    while len(frames_b64) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frames_b64.append(base64.b64encode(buffer).decode("utf-8"))
        frame_idx += frame_interval

    cap.release()
    return frames_b64


def get_video_frames_for_game(youtube_url: str, interval_seconds: float = 2.0) -> list[tuple[float, str]]:
    """
    Download video and extract frames.
    Returns list of (timestamp_seconds, base64_jpeg) tuples.
    """
    if "youtube.com/results" in youtube_url:
        # Search URL only — no direct video to download
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = download_video(youtube_url, tmpdir)
        if not video_path:
            return []

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        cap.release()

        frames_b64 = extract_frames(video_path, interval_seconds)
        result = []
        for i, b64 in enumerate(frames_b64):
            timestamp = i * interval_seconds
            result.append((timestamp, b64))
        return result
