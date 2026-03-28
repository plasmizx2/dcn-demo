"""
Auto-installer for Ollama and Whisper based on hardware tier.
"""

import subprocess
import shutil
import platform
import sys


def setup_dependencies(tier):
    """Install required tools based on capability tier."""
    print("\n[setup] Checking dependencies...")

    if tier >= 3:
        install_ollama()

    if tier >= 2:
        check_whisper()

    print("[setup] Dependencies ready.\n")


def install_ollama():
    """Install Ollama if not present, then pull a small model."""
    if shutil.which("ollama"):
        print("[setup] Ollama already installed.")
        _ensure_model()
        return

    print("[setup] Installing Ollama...")
    system = platform.system()

    try:
        if system == "Darwin":
            # macOS — use the install script
            subprocess.run(
                ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                check=True, timeout=120
            )
        elif system == "Linux":
            subprocess.run(
                ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                check=True, timeout=120
            )
        elif system == "Windows":
            print("[setup] Windows detected — please install Ollama manually from https://ollama.com")
            print("[setup] Skipping Ollama setup. Worker will run without LLM tasks.")
            return
        else:
            print(f"[setup] Unsupported OS: {system}. Skipping Ollama.")
            return

        print("[setup] Ollama installed successfully.")
        _ensure_model()

    except Exception as e:
        print(f"[setup] Failed to install Ollama: {e}")
        print("[setup] Worker will run without LLM tasks.")


def _ensure_model():
    """Pull llama3.2 if not already downloaded."""
    model = "llama3.2"
    print(f"[setup] Ensuring model '{model}' is available...")

    try:
        # Check if model exists
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10
        )
        if model in result.stdout:
            print(f"[setup] Model '{model}' already downloaded.")
            return

        # Pull it
        print(f"[setup] Downloading '{model}' (this may take a few minutes)...")
        subprocess.run(
            ["ollama", "pull", model],
            check=True, timeout=600
        )
        print(f"[setup] Model '{model}' ready.")

    except Exception as e:
        print(f"[setup] Failed to pull model: {e}")


def check_whisper():
    """Verify whisper is importable (installed via requirements.txt)."""
    try:
        import whisper
        print("[setup] Whisper is available.")
    except ImportError:
        print("[setup] Whisper not found. Installing...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "openai-whisper"],
                check=True, timeout=120, capture_output=True
            )
            print("[setup] Whisper installed.")
        except Exception as e:
            print(f"[setup] Failed to install Whisper: {e}")
