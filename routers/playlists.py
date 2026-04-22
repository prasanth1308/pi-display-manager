from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import MediaFile, Playlist, PlaylistItem

router = APIRouter()


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class PlaylistItemIn(BaseModel):
    media_file_id: int
    order: int
    duration: float = 10.0


class PlaylistIn(BaseModel):
    name: str
    items: list[PlaylistItemIn] = []


class MediaFileRef(BaseModel):
    id: int
    original_name: str
    file_type: str
    model_config = {"from_attributes": True}


class PlaylistItemOut(BaseModel):
    id: int
    media_file_id: int
    order: int
    duration: float
    media_file: MediaFileRef
    model_config = {"from_attributes": True}


class PlaylistOut(BaseModel):
    id: int
    name: str
    items: list[PlaylistItemOut]
    model_config = {"from_attributes": True}


class PlaylistSummary(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.get("/", response_model=list[PlaylistSummary])
def list_playlists(db: Session = Depends(get_db)):
    return db.query(Playlist).order_by(Playlist.created_at.desc()).all()


@router.post("/", response_model=PlaylistOut)
def create_playlist(data: PlaylistIn, db: Session = Depends(get_db)):
    _validate_items(data.items, db)
    playlist = Playlist(name=data.name)
    db.add(playlist)
    db.flush()
    _upsert_items(playlist.id, data.items, db)
    db.commit()
    db.refresh(playlist)
    return playlist


@router.get("/{playlist_id}", response_model=PlaylistOut)
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


@router.put("/{playlist_id}", response_model=PlaylistOut)
def update_playlist(playlist_id: int, data: PlaylistIn, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    _validate_items(data.items, db)
    playlist.name = data.name
    db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist_id).delete()
    _upsert_items(playlist_id, data.items, db)
    db.commit()
    db.refresh(playlist)
    return playlist


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _validate_items(items: list[PlaylistItemIn], db: Session):
    ids = {i.media_file_id for i in items}
    found = {r.id for r in db.query(MediaFile.id).filter(MediaFile.id.in_(ids)).all()}
    missing = ids - found
    if missing:
        raise HTTPException(status_code=400, detail=f"Media file(s) not found: {missing}")


def _upsert_items(playlist_id: int, items: list[PlaylistItemIn], db: Session):
    for item in items:
        db.add(PlaylistItem(
            playlist_id=playlist_id,
            media_file_id=item.media_file_id,
            order=item.order,
            duration=item.duration,
        ))
