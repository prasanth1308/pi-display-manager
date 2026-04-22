from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Playlist, Schedule
from scheduler_service import refresh_schedule, remove_schedule

router = APIRouter()


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class ScheduleIn(BaseModel):
    name: str
    playlist_id: int
    cron_expression: str
    is_active: bool = True


class ScheduleOut(BaseModel):
    id: int
    name: str
    playlist_id: int
    cron_expression: str
    is_active: bool

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.get("/", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(Schedule).order_by(Schedule.created_at.desc()).all()


@router.post("/", response_model=ScheduleOut)
def create_schedule(data: ScheduleIn, db: Session = Depends(get_db)):
    _validate_playlist(data.playlist_id, db)
    schedule = Schedule(**data.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    refresh_schedule(schedule.id, schedule.cron_expression, schedule.playlist_id, schedule.is_active)
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: int, data: ScheduleIn, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    _validate_playlist(data.playlist_id, db)
    for key, val in data.model_dump().items():
        setattr(schedule, key, val)
    db.commit()
    db.refresh(schedule)
    refresh_schedule(schedule.id, schedule.cron_expression, schedule.playlist_id, schedule.is_active)
    return schedule


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    remove_schedule(schedule_id)
    db.delete(schedule)
    db.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _validate_playlist(playlist_id: int, db: Session):
    if not db.query(Playlist).filter(Playlist.id == playlist_id).first():
        raise HTTPException(status_code=400, detail="Playlist not found")
