import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from converter import convert_to_images
from database import get_db
from models import MediaFile

router = APIRouter()

MEDIA_DIR = Path("media")
CONVERTED_DIR = Path("converted")
MEDIA_DIR.mkdir(exist_ok=True)
CONVERTED_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES: dict[str, list[str]] = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "video": [".mp4", ".avi", ".mkv", ".mov", ".webm"],
    "presentation": [".ppt", ".pptx", ".odp", ".pdf"],
}


class MediaFileOut(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    file_path: str
    converted_dir: Optional[str]

    model_config = {"from_attributes": True}


def _get_file_type(filename: str) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    for ftype, exts in ALLOWED_TYPES.items():
        if ext in exts:
            return ftype
    return None


@router.get("/", response_model=list[MediaFileOut])
def list_files(db: Session = Depends(get_db)):
    return db.query(MediaFile).order_by(MediaFile.created_at.desc()).all()


@router.post("/upload", response_model=MediaFileOut)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_type = _get_file_type(file.filename or "")
    if not file_type:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

    suffix = Path(file.filename).suffix.lower()
    unique_stem = str(uuid.uuid4())
    unique_name = unique_stem + suffix
    file_path = MEDIA_DIR / unique_name

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    converted_dir = None
    if file_type == "presentation":
        out_dir = CONVERTED_DIR / unique_stem
        try:
            convert_to_images(str(file_path), str(out_dir))
            converted_dir = str(out_dir)
        except Exception as e:
            # Clean up uploaded file on conversion failure
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=f"Conversion failed: {e}")

    media_file = MediaFile(
        filename=unique_name,
        original_name=file.filename,
        file_type=file_type,
        file_path=str(file_path),
        converted_dir=converted_dir,
    )
    db.add(media_file)
    db.commit()
    db.refresh(media_file)
    return media_file


@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    media_file = db.query(MediaFile).filter(MediaFile.id == file_id).first()
    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")

    Path(media_file.file_path).unlink(missing_ok=True)
    if media_file.converted_dir:
        shutil.rmtree(media_file.converted_dir, ignore_errors=True)

    db.delete(media_file)
    db.commit()
    return {"status": "deleted"}
