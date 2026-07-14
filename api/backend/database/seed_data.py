import os
import asyncio
import logging
from datetime import datetime, timezone
import json

from models.database import (
    Base, engine, async_session,
    Case, Statute, User, FlashcardDeck, StudyNote,
)
from services.scraper import scrape_constitution, scrape_statute, scrape_case

logger = logging.getLogger("juriscore")

LANDMARK_CASES = [
    {"title": "Republic v Daniel Toroitich arap Moi & 2 Others ex parte Gicheru", "court": "High Court", "year": 2016},
    {"title": "Mumo v Republic", "court": "Supreme Court", "year": 2013},
    {"title": "Mitu-Bell Welfare Society v Kenya Airports Authority", "court": "Supreme Court", "year": 2016},
    {"title": "Tangazo House Limited v Kenya Power & Lighting Company Limited", "court": "Court of Appeal", "year": 2019},
    {"title": "Njoya & 5 others v Attorney General & 2 others", "court": "High Court", "year": 2004},
]

STATUTES = [
    {"title": "Penal Code", "cap_number": "63"},
    {"title": "Law of Contract Act", "cap_number": "23"},
    {"title": "Evidence Act", "cap_number": "80"},
    {"title": "Criminal Procedure Code", "cap_number": "75"},
    {"title": "Employment Act", "cap_number": "226"},
]


async def seed_constitution(session):
    try:
        data = await scrape_constitution()
        statute = Statute(
            id="stat-constitution-2010",
            title=data.get("title", "Constitution of Kenya 2010"),
            citation="Constitution of Kenya, 2010",
            cap_number=None,
            full_text=data.get("full_text", ""),
            amendments=None,
        )
        session.add(statute)
        logger.info("Seeded Constitution")
    except Exception as e:
        logger.error(f"Failed to seed constitution: {e}")


async def seed_cases(session):
    for c in LANDMARK_CASES[:10]:
        try:
            text = f"{c['title']}\\n\\nThis is a placeholder for the full judgment text sourced from kenyalaw.org. The full text should be scraped at runtime."
            case = Case(
                title=c["title"],
                citation=f"[{c['year']}] {c['court']}",
                court=c["court"],
                year=c["year"],
                subject_tags=[],
                full_text=text,
                summary={"facts": "", "issues": [], "holdings": [], "ratio": "", "obiter": "", "cases_cited": []},
                ratio="",
                judges=[],
            )
            session.add(case)
            logger.info(f"Seeded case: {c['title']}")
        except Exception as e:
            logger.error(f"Failed to seed case {c['title']}: {e}")


async def seed_statutes(session):
    for s in STATUTES:
        try:
            text = f"{s['title']} (Cap. {s['cap_number']})\\n\\nFull statutory text would be scraped from kenyalaw.org/lex/ on first access."
            statute = Statute(
                title=s["title"],
                citation=f"Cap. {s['cap_number']}",
                cap_number=s["cap_number"],
                full_text=text,
                amendments=[],
            )
            session.add(statute)
            logger.info(f"Seeded statute: {s['title']}")
        except Exception as e:
            logger.error(f"Failed to seed statute {s['title']}: {e}")


async def seed_demo_user(session):
    user = User(
        id="user-demo",
        name="Demo Student",
        email="demo@juriscore.app",
        university="University of Nairobi",
    )
    session.add(user)
    logger.info("Seeded demo user")
    return user


async def seed_decks(user_id: str, session):
    decks = [
        ("Constitutional Law", "constitutional-law"),
        ("Criminal Law", "criminal-law"),
        ("Contract Law", "contract-law"),
        ("Evidence Law", "evidence"),
        ("Civil Procedure", "civil-procedure"),
    ]
    for title, subject in decks:
        deck = FlashcardDeck(user_id=user_id, title=title, subject=subject)
        session.add(deck)
    logger.info("Seeded flashcard decks")


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await seed_constitution(session)
        await seed_cases(session)
        await seed_statutes(session)
        user = await seed_demo_user(session)
        await seed_decks(user.id, session)
        await session.commit()
    logger.info("Seeding complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
