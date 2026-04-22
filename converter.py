"""
Converts presentation files (PPT, PPTX, ODP, PDF) to PNG images.

PPT/PPTX/ODP → LibreOffice headless → PNG
PDF           → pdftoppm (poppler)  → PNG
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_to_images(file_path: str, output_dir: str) -> list[str]:
    """
    Convert a presentation or PDF to a sorted list of PNG file paths.
    Raises RuntimeError on failure.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if ext == ".pdf":
        return _pdf_to_images(file_path, out)
    elif ext in {".ppt", ".pptx", ".odp"}:
        return _ppt_to_images(file_path, out)
    else:
        raise ValueError(f"Unsupported presentation format: {ext}")


def _ppt_to_images(file_path: str, out_dir: Path) -> list[str]:
    """Use LibreOffice headless to convert PPT → PNG slides."""
    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to", "png",
            "--outdir", str(out_dir),
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed: {result.stderr.strip()}"
        )

    images = sorted(out_dir.glob("*.png"), key=_slide_sort_key)
    if not images:
        raise RuntimeError("LibreOffice ran but produced no PNG files")

    logger.info("Converted %s → %d slides in %s", file_path, len(images), out_dir)
    return [str(p) for p in images]


def _pdf_to_images(file_path: str, out_dir: Path) -> list[str]:
    """Use pdftoppm (poppler-utils) to convert PDF → PNG slides."""
    stem = Path(file_path).stem
    prefix = str(out_dir / stem)

    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "150", file_path, prefix],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"pdftoppm conversion failed: {result.stderr.strip()}"
        )

    images = sorted(out_dir.glob(f"{stem}*.png"), key=_slide_sort_key)
    if not images:
        raise RuntimeError("pdftoppm ran but produced no PNG files")

    logger.info("Converted PDF %s → %d slides in %s", file_path, len(images), out_dir)
    return [str(p) for p in images]


def _slide_sort_key(path: Path) -> tuple:
    """Sort by embedded number so slide-2 comes before slide-10."""
    nums = re.findall(r"\d+", path.stem)
    return tuple(int(n) for n in nums) if nums else (0,)
