"""
Image processing handler — resize, compress, and analyze images.
Uses Pillow (no API keys needed).
"""

import io
import os
import time
import requests
import tempfile
from PIL import Image


def handle(task, job):
    """Process a batch of images: download, resize, compress, report stats."""
    payload = task.get("task_payload") or {}
    job_payload = job.get("input_payload") or {}

    image_urls = payload.get("image_urls") or job_payload.get("image_urls", [])
    target_width = job_payload.get("width", 800)
    quality = job_payload.get("quality", 80)

    if not image_urls:
        # Demo mode — generate a report about image processing capabilities
        return (
            "## Image Processing Report\n\n"
            "No image URLs provided. In production, this worker would:\n"
            "- Download images from provided URLs\n"
            "- Resize to target dimensions\n"
            "- Compress with specified quality\n"
            "- Convert between formats (PNG, JPEG, WebP)\n"
            "- Generate thumbnails\n"
            "- Report file size savings\n\n"
            f"**Worker capabilities:** Pillow {Image.__version__}\n"
            f"**Supported formats:** {', '.join(sorted(Image.OPEN.keys())[:20])}\n"
        )

    results = []
    for url in image_urls:
        try:
            start = time.time()
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()

            original_size = len(resp.content)
            img = Image.open(io.BytesIO(resp.content))
            original_dims = img.size

            # Resize maintaining aspect ratio
            ratio = target_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((target_width, new_height), Image.LANCZOS)

            # Compress to JPEG
            buffer = io.BytesIO()
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            compressed_size = buffer.tell()

            savings = round((1 - compressed_size / original_size) * 100, 1)
            elapsed = round(time.time() - start, 2)

            results.append(
                f"- **{url.split('/')[-1]}**: {original_dims[0]}x{original_dims[1]} -> "
                f"{target_width}x{new_height}, {original_size:,}B -> {compressed_size:,}B "
                f"({savings}% saved) [{elapsed}s]"
            )
        except Exception as e:
            results.append(f"- **{url}**: Failed — {e}")

    return (
        f"## Image Processing Results\n\n"
        f"Processed {len(image_urls)} images (target: {target_width}px, quality: {quality}%)\n\n"
        + "\n".join(results)
    )
