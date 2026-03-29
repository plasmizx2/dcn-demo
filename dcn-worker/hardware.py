"""
Hardware capability detection.
Determines what task types this worker can handle.
"""

import os
import platform
import shutil
import subprocess


def detect():
    """Return a dict of hardware capabilities."""
    info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "cores": os.cpu_count() or 1,
        "ram_gb": _get_ram_gb(),
        "has_gpu": _has_gpu(),
        "gpu_type": _gpu_type(),
        "free_disk_gb": _free_disk_gb(),
    }
    info["tier"] = _compute_tier(info)
    info["supported_task_types"] = _supported_types(info["tier"])
    return info


def _get_ram_gb():
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        return 0


def _has_gpu():
    return _gpu_type() is not None


def _gpu_type():
    # Check NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"nvidia:{result.stdout.strip().split(chr(10))[0]}"
        except Exception:
            pass

    # Check Apple Silicon (M1/M2/M3/M4)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "apple_silicon"

    # Check AMD ROCm
    if shutil.which("rocm-smi"):
        return "amd_rocm"

    # Check Windows WMI for any dedicated GPU
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command",
                 "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip().lower()
                    if any(kw in line for kw in ["radeon", "geforce", "nvidia", "amd", "rtx", "gtx", "rx "]):
                        return f"gpu:{result.stdout.strip().split(chr(10))[0].strip()}"
        except Exception:
            pass

    # Check Linux lspci for any GPU
    if platform.system() == "Linux" and shutil.which("lspci"):
        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA" in line or "3D controller" in line:
                        low = line.lower()
                        if any(kw in low for kw in ["radeon", "geforce", "nvidia", "amd", "rtx", "gtx", "rx "]):
                            name = line.split(":")[-1].strip()
                            return f"gpu:{name}"
        except Exception:
            pass

    return None


def _free_disk_gb():
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
        return round(usage.free / (1024 ** 3), 1)
    except Exception:
        return 0


def _compute_tier(info):
    """
    Tier 1: Any machine (image processing, web scraping, pdf extraction)
    Tier 2: 8GB+ RAM, 4+ cores (adds Whisper audio transcription)
    Tier 3: GPU or 16GB+ RAM (adds Ollama LLM tasks)
    """
    if info["has_gpu"] or info["ram_gb"] >= 16:
        return 3
    if info["ram_gb"] >= 8 and info["cores"] >= 4:
        return 2
    return 1


def _supported_types(tier):
    """Return list of task types this tier can handle."""
    types = ["image_processing", "web_scraping", "ml_experiment"]

    if tier >= 2:
        types.append("audio_transcription")

    if tier >= 3:
        types.append("sentiment_classification")

    return types


def print_report(info):
    """Pretty-print hardware detection results."""
    print("=" * 50)
    print("  DCN Worker — Hardware Detection")
    print("=" * 50)
    print(f"  OS:          {info['os']} ({info['arch']})")
    print(f"  CPU Cores:   {info['cores']}")
    print(f"  RAM:         {info['ram_gb']} GB")
    print(f"  GPU:         {info['gpu_type'] or 'None detected'}")
    print(f"  Free Disk:   {info['free_disk_gb']} GB")
    print(f"  Tier:        {info['tier']}")
    print(f"  Task Types:  {', '.join(info['supported_task_types'])}")
    print("=" * 50)
