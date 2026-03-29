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
    Tier 1: Any machine (image processing, web scraping, audio transcription)
    Tier 2: 8GB+ RAM, 4+ cores (adds ml_experiment)
    Tier 3: GPU or 16GB+ RAM, 8+ cores (adds sentiment_classification, LLM tasks)
    Tier 4: NVIDIA CUDA GPU + 100GB+ RAM + 16+ cores — high-end workstation / datacenter
             (adds large_scale_ml: massive distributed training, 500K+ row jobs)
    """
    # Tier 4: real NVIDIA GPU + 100GB+ RAM + 16+ cores
    gpu = info.get("gpu_type") or ""
    is_nvidia_cuda = gpu.startswith("nvidia:")
    if is_nvidia_cuda and info["ram_gb"] >= 100 and info["cores"] >= 16:
        return 4
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

    if tier >= 4:
        types.append("large_scale_ml")

    return types


def print_report(info):
    """Pretty-print hardware detection results."""
    tier_labels = {
        1: "Tier 1 — Basic (any machine)",
        2: "Tier 2 — Standard (8GB+ RAM, 4+ cores)",
        3: "Tier 3 — Enhanced (GPU or 16GB+ RAM)",
        4: "Tier 4 — Datacenter (NVIDIA GPU + 100GB+ RAM + 16+ cores)",
    }
    print("=" * 60)
    print("  DCN Worker — Hardware Detection")
    print("=" * 60)
    print(f"  OS:          {info['os']} ({info['arch']})")
    print(f"  CPU Cores:   {info['cores']}")
    print(f"  RAM:         {info['ram_gb']} GB")
    print(f"  GPU:         {info['gpu_type'] or 'None detected'}")
    print(f"  Free Disk:   {info['free_disk_gb']} GB")
    print(f"  Tier:        {info['tier']} — {tier_labels.get(info['tier'], 'Unknown')}")
    print(f"  Task Types:  {', '.join(info['supported_task_types'])}")
    print("=" * 60)
