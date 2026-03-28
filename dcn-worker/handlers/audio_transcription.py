"""
Audio transcription handler — transcribe audio files using OpenAI Whisper.
Runs 100% locally, no API keys needed.
Requires: openai-whisper (pip install openai-whisper)
"""

import os
import time
import tempfile
import requests


# Lazy-load whisper to avoid import errors on Tier 1 machines
_whisper = None
_model = None


def _get_model():
    global _whisper, _model
    if _model is None:
        import whisper
        _whisper = whisper
        # Use "base" model — good balance of speed and accuracy, ~150MB
        print("[whisper] Loading model (first time may download ~150MB)...")
        _model = whisper.load_model("base")
        print("[whisper] Model loaded.")
    return _model


def handle(task, job):
    """Transcribe audio files from URLs using Whisper."""
    payload = task.get("task_payload") or {}
    job_payload = job.get("input_payload") or {}

    audio_urls = payload.get("audio_urls") or job_payload.get("audio_urls", [])

    if not audio_urls:
        # Demo mode
        try:
            model = _get_model()
            return (
                "## Audio Transcription Report\n\n"
                "No audio URLs provided. Whisper model loaded successfully.\n\n"
                "In production, this worker would:\n"
                "- Download audio files (MP3, WAV, M4A, etc.)\n"
                "- Transcribe speech to text using OpenAI Whisper\n"
                "- Detect language automatically\n"
                "- Return timestamped transcriptions\n\n"
                f"**Model:** base | **Supported languages:** 99+\n"
            )
        except Exception as e:
            return f"## Audio Transcription\n\nWhisper not available: {e}"

    model = _get_model()
    results = []

    for url in audio_urls:
        try:
            start = time.time()
            filename = url.split("/")[-1].split("?")[0] or "audio"

            # Download audio to temp file
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".mp3", delete=False) as f:
                f.write(resp.content)
                temp_path = f.name

            # Transcribe
            result = model.transcribe(temp_path)
            elapsed = round(time.time() - start, 2)

            text = result.get("text", "").strip()
            language = result.get("language", "unknown")

            # Clean up
            os.unlink(temp_path)

            results.append(
                f"### {filename}\n"
                f"**Language:** {language} | **Time:** {elapsed}s | **Size:** {len(resp.content):,}B\n\n"
                f"{text}\n"
            )

        except Exception as e:
            results.append(f"### {url}\n**Error:** {e}\n")

    return (
        f"## Transcription Results\n\n"
        f"Transcribed {len(audio_urls)} files\n\n"
        + "\n---\n\n".join(results)
    )
