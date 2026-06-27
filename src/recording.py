"""Audio recording module — mic capture and macOS sleep prevention.

Handles:
  - Microphone recording via miniaudio CaptureDevice
  - macOS-specific: readiness sound, GUI stop button, sleep prevention
  - Platform-safe: Linux recording works, macOS extras are guarded
"""

import array
import subprocess
import sys
import tempfile
import time

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
    # Lazy import — miniaudio CFFI extension may not be available on
    # headless CI runners without audio hardware
    import miniaudio

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

    # Generator receives audio chunks from CaptureDevice via .send()
    frames = array.array("h")  # signed 16-bit PCM

    def capture_generator():
        try:
            while True:
                data = yield
                frames.extend(data)
        except GeneratorExit:
            pass

    gen = capture_generator()
    next(gen)  # Prime the generator

    capture = miniaudio.CaptureDevice(
        sample_rate=RECORDING_SAMPLERATE,
        nchannels=1,
        input_format=miniaudio.SampleFormat.SIGNED16,
    )

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
        capture.start(gen)
        while True:
            # Check if Stop button was clicked
            if btn_process and btn_process.poll() is not None:
                print("\n🛑 Stop button clicked.")
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Recording stopped.")
    finally:
        capture.stop()
        capture.close()
        # Dismiss the dialog if still open
        if btn_process and btn_process.poll() is None:
            btn_process.terminate()

    duration_s = len(frames) / RECORDING_SAMPLERATE
    print(f"💾 Saving recording ({duration_s:.1f}s)...")

    sound = miniaudio.DecodedSoundFile(
        name="recording",
        nchannels=1,
        sample_rate=RECORDING_SAMPLERATE,
        sample_format=miniaudio.SampleFormat.SIGNED16,
        samples=frames,
    )
    miniaudio.wav_write_file(output_path, sound)
    return output_path
