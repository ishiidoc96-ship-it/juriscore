from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from api.backend.models.database import FlashcardDeck, Flashcard
from api.backend.models.schemas import FlashcardDeckCreate, FlashcardDeckResponse, FlashcardCreate, FlashcardResponse, FlashcardUpdate
from api.backend.core import get_session
from datetime import datetime
import logging

from api.backend.routers.auth import get_current_user
from api.backend.models.database import User

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.get("/decks", response_model=List[FlashcardDeckResponse])
async def list_decks(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FlashcardDeck).where(FlashcardDeck.user_id == current_user.id))
    decks = result.scalars().all()
    return [
        FlashcardDeckResponse(id=d.id, user_id=d.user_id, title=d.title, subject=d.subject, created_at=d.created_at)
        for d in decks
    ]


@router.post("/decks", response_model=FlashcardDeckResponse)
async def create_deck(payload: FlashcardDeckCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    deck = FlashcardDeck(user_id=current_user.id, title=payload.title, subject=payload.subject)
    session.add(deck)
    await session.flush()
    await session.commit()
    return FlashcardDeckResponse(id=deck.id, user_id=deck.user_id, title=deck.title, subject=deck.subject, created_at=deck.created_at)


@router.get("/decks/{deck_id}", response_model=FlashcardDeckResponse)
async def get_deck(deck_id: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == current_user.id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return FlashcardDeckResponse(id=deck.id, user_id=deck.user_id, title=deck.title, subject=deck.subject, created_at=deck.created_at)


@router.post("/decks/{deck_id}/cards", response_model=FlashcardResponse)
async def add_card(deck_id: str, payload: FlashcardCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == current_user.id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    card = Flashcard(deck_id=deck_id, front=payload.front, back=payload.back)
    session.add(card)
    await session.flush()
    await session.commit()
    return FlashcardResponse(
        id=card.id,
        deck_id=card.deck_id,
        front=card.front,
        back=card.back,
        interval=card.interval,
        ease_factor=card.ease_factor,
        next_review=card.next_review,
        created_at=card.created_at,
    )


@router.put("/cards/{card_id}", response_model=FlashcardResponse)
async def update_card(card_id: str, payload: FlashcardUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Flashcard).join(FlashcardDeck).where(Flashcard.id == card_id, FlashcardDeck.user_id == current_user.id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.interval = payload.interval
    card.ease_factor = payload.ease_factor
    card.next_review = payload.next_review
    await session.commit()
    return FlashcardResponse(
        id=card.id,
        deck_id=card.deck_id,
        front=card.front,
        back=card.back,
        interval=card.interval,
        ease_factor=card.ease_factor,
        next_review=card.next_review,
        created_at=card.created_at,
    )


@router.get("/decks/{deck_id}/due", response_model=List[FlashcardResponse])
async def due_cards(deck_id: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == current_user.id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    now = datetime.utcnow()
    result = await session.execute(
        select(Flashcard).where(Flashcard.deck_id == deck_id, Flashcard.next_review <= now)
    )
    cards = result.scalars().all()
    return [
        FlashcardResponse(
            id=c.id,
            deck_id=c.deck_id,
            front=c.front,
            back=c.back,
            interval=c.interval,
            ease_factor=c.ease_factor,
            next_review=c.next_review,
            created_at=c.created_at,
        )
        for c in cards
    ]


@router.delete("/decks/{deck_id}")
async def delete_deck(deck_id: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == current_user.id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    await session.delete(deck)
    await session.commit()
    return {"status": "deleted"}
