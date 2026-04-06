"""Artist preference endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserArtistPreference

router = APIRouter(prefix="/me/artists", tags=["artists"])

MAX_ARTISTS_PER_GENRE = 3


class AddArtistRequest(BaseModel):
    artist_name: str
    musicbrainz_id: str | None = None
    mb_genres: list[str] | None = None
    genre_context: str


class ArtistResponse(BaseModel):
    id: int
    artist_name: str
    musicbrainz_id: str | None
    mb_genres: list[str] | None
    genre_context: str
    weight: float

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ArtistResponse])
async def get_artists(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtistPreference).where(UserArtistPreference.user_id == user.id)
    )
    return result.scalars().all()


@router.post("", response_model=ArtistResponse, status_code=status.HTTP_201_CREATED)
async def add_artist(
    body: AddArtistRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check max 3 per genre
    result = await db.execute(
        select(UserArtistPreference).where(
            UserArtistPreference.user_id == user.id,
            UserArtistPreference.genre_context == body.genre_context,
        )
    )
    existing = result.scalars().all()
    if len(existing) >= MAX_ARTISTS_PER_GENRE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_ARTISTS_PER_GENRE} artists per genre.",
        )

    artist = UserArtistPreference(
        user_id=user.id,
        artist_name=body.artist_name,
        musicbrainz_id=body.musicbrainz_id,
        mb_genres=body.mb_genres,
        genre_context=body.genre_context,
    )
    db.add(artist)
    await db.flush()
    # NOTE: do NOT call db.commit() here — get_db dependency handles the commit
    await db.refresh(artist)
    return artist


@router.delete("/{artist_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_artist(
    artist_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtistPreference).where(
            UserArtistPreference.user_id == user.id,
            UserArtistPreference.artist_name == artist_name,
        )
    )
    artist = result.scalar_one_or_none()
    if artist:
        await db.delete(artist)
        # NOTE: do NOT call db.commit() here — get_db dependency handles the commit
