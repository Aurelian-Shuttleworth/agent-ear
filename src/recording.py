"""Audio recording module — mic capture and macOS sleep prevention.

Handles:
  - Microphone recording via sounddevice InputStream
  - macOS-specific: readiness sound, GUI stop button, sleep prevention
  - Platform-safe: Linux recording works, macOS extras are guarded
"""

import subprocess
import sys
import tempfile
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import RECORDING_SAMPLERATE


class SleepPrevention:
    """Prevent macOS sleep during recording/transcription."""

    def __enter__(self):
        self._proc = None
        if sys.platform == "darwin":
            self._proc = subprocess.Popen(
                ["caffeinate", "-dimsu"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return self

    def __exit__(self, *args):
        if self._proc:
            self._proc.terminate()
            self._proc.wait()


def record_audio() -> str:
    """Record audio from microphone until Ctrl+C or Stop button (macOS).

    Returns:
        Path to temporary WAV file containing the recording.
    """
    tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output_path = tf.name
    tf.close()

    # Play readiness sound (macOS)
    if sys.platform == "darwin":
        try:
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"])
        except Exception:
            pass

    print("🎙️  Recording... Press Ctrl+C to stop.")
    q = []

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.append(indata.copy())

    # Launch macOS stop-button dialog
    btn_process = None
    if sys.platform == "darwin":
        try:
            script = (
                'display dialog "🎙️ Anti-Gravity Agent-Ear\\n\\n'
                'Click Stop to finish recording." '
                'buttons {"Stop"} default button "Stop" '
                'with icon note with title "Anti-Gravity"'
            )
            btn_process = subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"⚠️ Could not launch GUI button: {e}")

    try:
        with sd.InputStream(
            samplerate=RECORDING_SAMPLERATE, channels=1, callback=callback
        ):
            while True:
                # Check if Stop button was clicked
                if btn_process and btn_process.poll() is not None:
                    print("\n🛑 Stop button clicked.")
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Recording stopped.")
    finally:
        # Dismiss the dialog if still open
        if btn_process and btn_process.poll() is None:
            btn_process.terminate()

    recording = np.concatenate(q)
    print(f"💾 Saving recording ({len(recording) / RECORDING_SAMPLERATE:.1f}s)...")
    sf.write(output_path, recording, RECORDING_SAMPLERATE)
    return output_path
