from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import MediaFile, Playlist
from player import player

router = APIRouter()


class PlayRequest(BaseModel):
    playlist_id: Optional[int] = None
    file_id: Optional[int] = None


@router.post("/play")
def play(request: PlayRequest, db: Session = Depends(get_db)):
    if request.playlist_id:
        playlist = db.query(Playlist).filter(Playlist.id == request.playlist_id).first()
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")
        if not playlist.items:
            raise HTTPException(status_code=400, detail="Playlist is empty")

        items = _build_items(playlist)
        player.play_playlist(items)
        return {"status": "playing", "playlist": playlist.name}

    elif request.file_id:
        mf = db.query(MediaFile).filter(MediaFile.id == request.file_id).first()
        if not mf:
            raise HTTPException(status_code=404, detail="File not found")

        items = _build_items_from_file(mf)
        player.play_playlist(items, loop=False)
        return {"status": "playing", "file": mf.original_name}

    raise HTTPException(status_code=400, detail="Provide playlist_id or file_id")


@router.post("/pause")
def pause():
    player.pause()
    return {"status": "paused"}


@router.post("/resume")
def resume():
    player.resume()
    return {"status": "resumed"}


@router.post("/stop")
def stop():
    player.stop()
    return {"status": "stopped"}


@router.post("/next")
def next_item():
    player.next()
    return {"status": "next"}


@router.get("/status")
def status():
    return player.get_status()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_items(playlist: Playlist) -> list[dict]:
    items = []
    for pi in playlist.items:
        mf = pi.media_file
        if mf.file_type == "presentation" and mf.converted_dir:
            # Expand slides as individual image items
            slides = sorted(Path(mf.converted_dir).glob("*.png"))
            for slide in slides:
                items.append({"path": str(slide), "type": "image", "duration": pi.duration})
        else:
            items.append({"path": mf.file_path, "type": mf.file_type, "duration": pi.duration})
    return items


def _build_items_from_file(mf: MediaFile) -> list[dict]:
    if mf.file_type == "presentation" and mf.converted_dir:
        slides = sorted(Path(mf.converted_dir).glob("*.png"))
        return [{"path": str(s), "type": "image", "duration": 10.0} for s in slides]
    return [{"path": mf.file_path, "type": mf.file_type, "duration": 10.0}]
