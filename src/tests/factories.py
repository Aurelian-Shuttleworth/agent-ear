"""Test factories — programmatic fixture generation.

Keeps conftest.py lean by centralising data generation.
Uses tmp_path for automatic cleanup.
"""

import struct
import wave


def create_wav(path, duration_s=1.0, sample_rate=44100, channels=1):
    """Generate a silent WAV file programmatically.

    Uses stdlib wave + struct — no external dependencies.
    Produces 16-bit signed PCM at the given sample rate.

    Args:
        path: Path object or string for the output file.
        duration_s: Duration in seconds.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.

    Returns:
        The path argument (for chaining).
    """
    num_samples = int(duration_s * sample_rate)
    frames = struct.pack(f"<{num_samples * channels}h", *([0] * num_samples * channels))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path
