from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)          # UUID-based stored name
    original_name = Column(String, nullable=False)     # Original upload name
    file_type = Column(String, nullable=False)         # image | video | presentation
    file_path = Column(String, nullable=False)         # Absolute path to stored file
    # For presentations: path to first slide PNG (used as thumbnail)
    converted_dir = Column(String, nullable=True)      # Directory of PNG slides
    created_at = Column(DateTime, default=datetime.utcnow)

    playlist_items = relationship(
        "PlaylistItem", back_populates="media_file", cascade="all, delete-orphan"
    )


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship(
        "PlaylistItem",
        back_populates="playlist",
        order_by="PlaylistItem.order",
        cascade="all, delete-orphan",
    )
    schedules = relationship("Schedule", back_populates="playlist")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"))
    media_file_id = Column(Integer, ForeignKey("media_files.id", ondelete="CASCADE"))
    order = Column(Integer, nullable=False)
    duration = Column(Float, default=10.0)  # seconds to display (images/slides)

    playlist = relationship("Playlist", back_populates="items")
    media_file = relationship("MediaFile", back_populates="playlist_items")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    playlist_id = Column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"))
    cron_expression = Column(String, nullable=False)  # e.g. "0 9 * * 1-5"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    playlist = relationship("Playlist", back_populates="schedules")
