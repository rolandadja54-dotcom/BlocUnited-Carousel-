"""
fal.ai image client (queue API) for the BlocUnited carousel pipeline.
=====================================================================

Generates imagery from a text prompt via fal.ai using the QUEUE endpoint
(submit -> poll status -> fetch result) — the same flow the existing n8n nodes
use for `nano-banana-pro`. The key is read from FAL_KEY / FAL_API_KEY env; it is
NEVER hardcoded. (Your n8n JSON currently has the key in plaintext — move it to a
credential / env var and rotate it.)

    from fal_image import generate
    generate("cinematic dark server room, glowing blue terminal, 4:5", "out/cover.png")

Model guide (override via arg or FAL_MODEL env):
  - photoreal scene / section art .. fal-ai/flux/dev
  - your current cover model ........ fal-ai/nano-banana-pro   (Gemini, strong)
  - fast drafts .................... fal-ai/flux/schnell
"""

from __future__ import annotations

import os
import time
from typing import Optional

QUEUE_ROOT = "https://queue.fal.run/"

MODELS = {
    "flux":      "fal-ai/flux/dev",
    "flux-fast": "fal-ai/flux/schnell",
    "flux-pro":  "fal-ai/flux-pro/v1.1",
    "nano":      "fal-ai/nano-banana-pro",
    "recraft":   "fal-ai/recraft-v3",
    "ideogram":  "fal-ai/ideogram/v2",
}
DEFAULT_MODEL = os.environ.get("FAL_MODEL", "flux")


def _api_key() -> str:
    key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if not key:
        raise RuntimeError(
            "No fal.ai key found. Set FAL_KEY (or FAL_API_KEY) in the environment."
        )
    return key


def _headers():
    return {"Authorization": f"Key {_api_key()}", "Content-Type": "application/json"}


def generate(prompt: str, out_path: str, model: str = DEFAULT_MODEL,
             width: int = 1080, height: int = 1350, aspect_ratio: str = "4:5",
             image_urls: Optional[list] = None, extra: Optional[dict] = None,
             poll_interval: float = 2.0, timeout: float = 180.0) -> str:
    """
    Generate one image for `prompt` and save it to `out_path`. Returns out_path.
    Uses the fal queue API: submit the job, poll until COMPLETED, download.
    `image_urls` — supply for edit models (e.g. nano-banana-pro/edit).
    Raises on missing key / HTTP / timeout (caller decides the fallback).
    """
    try:
        import requests
    except ImportError as e:                       # pragma: no cover
        raise RuntimeError("The 'requests' package is required (pip install requests).") from e

    model_id = MODELS.get(model, model)
    payload = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "num_images": 1,
    }
    if image_urls:
        payload["image_urls"] = image_urls
    if extra:
        payload.update(extra)

    # 1) submit
    sub = requests.post(QUEUE_ROOT + model_id, json=payload, headers=_headers(), timeout=60)
    sub.raise_for_status()
    job = sub.json()

    # some models answer synchronously; if images are already here, use them
    result = job if job.get("images") else None
    status_url = job.get("status_url")
    response_url = job.get("response_url")

    # 2) poll
    if result is None and status_url:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            st = requests.get(status_url, headers=_headers(), timeout=60).json()
            status = (st.get("status") or "").upper()
            if status in ("COMPLETED", "OK", "SUCCESS"):
                break
            if status in ("FAILED", "ERROR", "CANCELLED"):
                raise RuntimeError(f"fal.ai job {status} for: {prompt[:50]}...")
            time.sleep(poll_interval)
        else:
            raise RuntimeError(f"fal.ai job timed out after {timeout}s")
        # 3) fetch result
        result = requests.get(response_url or status_url, headers=_headers(), timeout=60).json()

    images = result.get("images") or result.get("image") or []
    if isinstance(images, dict):
        images = [images]
    if not images:
        raise RuntimeError(f"fal.ai returned no images for: {prompt[:50]}...")
    url = images[0]["url"]

    img_bytes = requests.get(url, timeout=120).content
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(img_bytes)
    return out_path


if __name__ == "__main__":               # smoke test (needs FAL_KEY)
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "a glowing blue neural network, dark navy, 4:5"
    print("Saved ->", generate(p, "out/_fal_test.png"))
