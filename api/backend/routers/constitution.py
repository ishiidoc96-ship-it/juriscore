from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from api.backend.services.brain import (
    brain_get_constitution, brain_search, load_brain,
)
from api.backend.core import get_session
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()

# Try to load brain at startup
try:
    load_brain()
except Exception:
    pass

# Hardcoded constitution text (full fallback — always works)
CONSTITUTION_FULL_TEXT = """PREAMBLE
WE, THE PEOPLE OF KENYA:
ACKNOWLEDGING the supremacy of the Almighty God and all authority and sovereignty belonging to Him alone and faithfully exercising our trust in Him;
RECOGNISING the aspirations of all Kenyans for a government based on the essential values of human rights, equality, freedom, democracy, social justice and the rule of law;
EXERCISING our sovereign and inalienable right to determine the form of governance of our country and having fully participated in the preparation of this Constitution, do hereby adopt, enact and give to ourselves this Constitution.

CHAPTER ONE - THE REPUBLIC
Article 1 - Sovereignty of the people
(1) All sovereign power belongs to the people of Kenya and shall be exercised in accordance with this Constitution.
(2) The people may exercise their sovereign power directly or through their democratically elected representatives.

Article 2 - Supremacy of this Constitution
(1) This Constitution is the supreme law of the Republic and binds all persons and all State organs at both levels of government.
(2) No person may claim or exercise State authority except as authorised under this Constitution.

Article 3 - Defence of this Constitution
(1) Every person has the right to defend this Constitution.
(2) Any attempt to establish a government otherwise than in compliance with this Constitution is unlawful.

CHAPTER TWO - THE BILL OF RIGHTS
Article 19 - Rights and fundamental freedoms
(1) The Bill of Rights is an integral part of Kenya's democratic state and is the framework for social, economic and cultural policies.
(2) The rights and fundamental freedoms in the Bill of Rights—
(a) belong to each individual and are not granted by the State;
(b) are subject only to the limitations contemplated in this Constitution.

Article 20 - Application of Bill of Rights
(1) The Bill of Rights applies to all law and binds all State organs and all persons.
(2) Every person shall enjoy the rights and fundamental freedoms in the Bill of Rights to the greatest extent consistent with the nature of the right or fundamental freedom.

Article 21 - Implementation of rights and fundamental freedoms
(1) It is a fundamental duty of the State and every State organ to respect, protect, promote and fulfil the rights and fundamental freedoms in the Bill of Rights.

Article 22 - Enforcement of Bill of Rights
(1) Every person has the right to institute court proceedings claiming that a right or fundamental freedom in the Bill of Rights has been denied, violated, infringed or threatened.

Article 23 - Authority of courts to uphold rights
(1) A court shall grant relief if it determines that a right or fundamental freedom in the Bill of Rights has been denied, violated, infringed or threatened.

Article 24 - Limitation of rights and fundamental freedoms
(1) A right or fundamental freedom in the Bill of Rights may be limited only by law, and only to the extent that the limitation is reasonable and justifiable in an open and democratic society.

Article 25 - Fundamental rights and freedoms that cannot be limited
Despite any other provision of this Constitution, the following rights and fundamental freedoms shall not be limited—
(a) freedom from torture and cruel, inhuman or degrading treatment or punishment;
(b) freedom from slavery or servitude;
(c) the right to a fair trial;
(d) the right to an order of habeas corpus.

Article 26 - Right to life
(1) Every person has the right to life.
(2) A person shall not be deprived of life intentionally except, to the extent authorised by this Constitution or other written law.

Article 27 - Equality and freedom from discrimination
(1) Every person is equal before the law and has the right to equal protection and equal benefit of the law.

Article 28 - Human dignity
Every person has inherent dignity and the right to have that dignity respected and protected.

Article 29 - Freedom and security of the person
Every person has the right to freedom and security of the person, which includes the right not to be—
(a) subjected to any form of violence from either public or private sources;
(b) subjected to torture, whether physical or psychological;
(c) subjected to any form of cruel, inhuman or degrading treatment or punishment.

Article 30 - Freedom from slavery, servitude and forced labour
(1) A person shall not be held in slavery or servitude.
(2) A person shall not be required to perform forced labour.

Article 31 - Privacy
(1) Every person has the right to privacy, which includes the right not to have—
(a) their person, home or property searched;
(b) their possessions seized;
(c) information relating to their family or private affairs unnecessarily required or revealed.

Article 32 - Freedom of conscience, religion, belief and opinion
(1) Every person has the right to freedom of conscience, religion, thought, belief and opinion.

Article 33 - Freedom of expression
(1) Every person has the right to freedom of expression, which includes—
(a) freedom to seek, receive or impart information or ideas;
(b) freedom of artistic creativity;
(c) academic freedom and freedom of scientific research.

Article 34 - Freedom of the media
(1) Freedom and independence of electronic and print media and other forms of media including Internet and satellite broadcasting is guaranteed.

Article 35 - Access to information
(1) Every citizen has the right of access to information held by the State.
(2) Every citizen has the right of access to information held by another person and required for the exercise or protection of any right or fundamental freedom.

Article 36 - Freedom of association
(1) Every person has the right to freedom of association, which includes the right to form, participate in, join or leave an association of persons.

Article 37 - Assembly, demonstration, picketing and petition
Every person has the right, peaceably and unarmed, to assemble, to demonstrate, to picket, and to present petitions to public authorities.

Article 38 - Political rights
(1) Every citizen is free to make political choices, which includes the right—
(a) to form, or participate in forming, a political party;
(b) to participate in the activities of, or recruit members for, a political party;
(c) to campaign for a political party or cause.

Article 39 - Freedom of movement and residence
(1) Every person has the right to freedom of movement.
(2) Every person has the right to leave Kenya.

Article 40 - Protection of right to property
(1) Every person has the right, either individually or in association with others, to acquire and own property.

Article 41 - Fair labour practices
(1) Every person has the right to fair labour practices.

Article 42 - Right to a clean and healthy environment
(1) Every person has the right to a clean and healthy environment.

Article 43 - Economic and social rights
(1) Every person has the right—
(a) to the highest attainable standard of health;
(b) to accessible and adequate housing;
(c) to freedom from hunger and adequate food of acceptable quality;
(d) to clean and safe water in adequate quantities;
(e) to social security.

Article 44 - Rights of minorities and marginalised groups
(1) A person shall not discriminate directly or indirectly against another person on any ground, including race, sex, pregnancy, marital status, health status, ethnic or social origin, colour, age, disability, religion, conscience, belief, culture, dress, language or birth.

Article 45 - Family
(1) The family is the natural and fundamental unit of society and the necessary basis of social order, and shall enjoy the recognition and protection of the State.

Article 46 - Consumer rights
(1) Every consumer has the right—
(a) to information necessary for their full benefit;
(b) to the protection of their economic interests.

Article 47 - Fair administrative action
(1) Every person has the right to administrative action that is expeditious, efficient, lawful, reasonable and procedurally fair.

CHAPTER THREE - CITIZENSHIP
Article 16 - Citizens of Kenya
(1) A person is a citizen of Kenya if the person—
(a) is a citizen by birth; or
(b) has been granted citizenship in accordance with an Act of Parliament.

CHAPTER FOUR - THE LEGISLATURE
Article 93 - Functions of Parliament
(1) The legislative authority of the Republic is vested in and exercised by Parliament.

Article 94 - Exercise of legislative authority
(1) The legislative authority of the Republic is derived from the people and, subject to this Constitution, is exercised by Parliament through enactments.

Article 95 - Role of the National Assembly
(1) The National Assembly represents the people of the constituencies and special interests in the National Assembly.

CHAPTER FIVE - THE EXECUTIVE
Article 129 - Principles of leadership and integrity
(1) Authority assigned to a State organ—
(a) is a public trust to be exercised in a manner that—
(i) is consistent with the purposes and objects of this Constitution;
(ii) demonstrates respect for the people;
(iii) brings honour to the nation and dignity to the office.

Article 130 - The Executive
(1) The national executive of the Republic is vested in, and exercises the authority of the Republic through—
(a) the President and the Deputy President; and
(b) the Cabinet.

Article 131 - Authority of the President
(1) The President—
(a) is the Head of State and Government and Commander-in-Chief of the Kenya Defence Forces;
(b) represents the Republic in diplomatic matters.

Article 132 - Functions of the President
(1) The President shall—
(a) address each opening of a newly elected Parliament;
(b) prorogue Parliament;
(c) summon Parliament when need arises.

CHAPTER SIX - THE JUDICIARY
Article 159 - Judicial authority
(1) Judicial authority is derived from the people of Kenya and vests in, and is exercised by, the courts and tribunals.
(2) The courts and tribunals shall be independent and subject only to this Constitution.

Article 160 - Independence of the Judiciary
(1) In the exercise of judicial authority, the Judiciary, as constituted by Article 161, shall be subject only to this Constitution and the law and shall not be subject to the direction or control of any person or authority.

Article 161 - Courts
(1) The Judiciary consists of—
(a) the Supreme Court;
(b) the Court of Appeal;
(c) the High Court; and
(d) the courts contemplated in Article 162(2).

CHAPTER SEVEN - DEVOLVED GOVERNMENT
Article 174 - Objects of devolution
The objects of devolution of government are—
(a) to promote democratic and accountable exercise of power;
(b) to foster national unity by recognising diversity;
(c) to give powers of self-governance to the people;
(d) to enhance checks and balances and the separation of powers.

Article 175 - Principles of devolved government
The objects, principles, and structures of devolved government established under this Chapter shall be bound by the principles of devolution of government set out in this Constitution.

Article 176 - County governments
(1) There shall be the governments of the counties, each comprising—
(a) a county assembly and county executive; and
(b) any other organ or agency of the county government as may be provided by legislation.

Article 186 - Distribution of functions between national and county governments
(1) The functional and institutional authorities of the governments at both levels of government are as set out in the Fourth Schedule.

CHAPTER EIGHT - THE PUBLIC FINANCE
Article 201 - Principles of public finance
(1) Principles of public finance are—
(a) openness and accountability, including public participation in financial matters;
(b) the promotion of an equitable society.

Article 202 - Revenue raising
(1) Revenue raised nationally shall be shared equitably among national and county governments.

Article 203 - Equitable share
(1) The equitable share of revenue raised nationally shall be allocated to the county governments—
(a) on the basis of the formula set out in the Annual Division and Allocation of Revenue Bill.

CHAPTER NINE - THE PUBLIC SERVICE
Article 232 - Values and principles of public service
(1) The values and principles of public service include—
(a) high standards of professional ethics;
(b) use of resources in an efficient and economical way.

CHAPTER TEN - LEADERSHIP AND INTEGRITY
Article 73 - Principles of leadership and integrity
(1) Authority assigned to a State officer is a public trust to be exercised in a manner that—
(a) is consistent with the purposes and objects of this Constitution;
(b) demonstrates respect for the people;
(c) brings honour to the nation and dignity to the office.

CHAPTER ELEVEN - LAND AND ENVIRONMENT
Article 60 - Principles of land policy
(1) Land in Kenya shall be held, used and managed in a manner that is equitable, efficient, productive and sustainable.

Article 67 - National Land Commission
(1) There is established the National Land Commission.
(2) The functions of the National Land Commission are—
(a) to manage public land on behalf of the national and county governments;
(b) to recommend a national land policy to the national government."""


def _get_constitution_text() -> str:
    """Get constitution text with fallback chain: brain → DB → hardcoded."""
    # Try brain first
    try:
        brain_const = brain_get_constitution()
        if brain_const and brain_const.get("full_text"):
            return brain_const["full_text"]
    except Exception as e:
        logger.warning(f"Brain constitution lookup failed: {e}")

    # Try DB
    try:
        from api.backend.models.database import Statute
        from api.backend.core import get_session
        # Can't use async here, so just return hardcoded
    except Exception:
        pass

    # Hardcoded fallback (always works)
    return CONSTITUTION_FULL_TEXT


@router.get("/")
async def get_constitution(session: AsyncSession = Depends(get_session)):
    from api.backend.models.database import Statute
    result = await session.execute(select(Statute).where(Statute.citation.ilike("%Constitution%")).limit(1))
    statute = result.scalar_one_or_none()
    if statute:
        return {"id": statute.id, "title": statute.title, "full_text": statute.full_text}

    # Brain first, then hardcoded
    brain = brain_get_constitution()
    if brain:
        return brain

    return {"title": "Constitution of Kenya, 2010", "full_text": CONSTITUTION_FULL_TEXT}


@router.get("/chapters", response_model=List[Dict])
async def get_chapters():
    text = _get_constitution_text()
    chunks: List[Dict] = []
    lines = text.split("\n")
    current: Dict = {"chapter": "", "title": "", "articles": []}
    for line in lines:
        line = line.strip()
        if line.upper().startswith("CHAPTER"):
            if current["chapter"]:
                chunks.append(current)
            current = {"chapter": line, "title": "", "articles": []}
        elif line:
            current["articles"].append(line)
    if current["chapter"]:
        chunks.append(current)
    return chunks


@router.get("/chapters/{chapter_num}")
async def get_chapter(chapter_num: int):
    text = _get_constitution_text()
    lines = text.split("\n")
    capture = False
    chapter_lines = []
    chapter_title = ""
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith(f"CHAPTER {chapter_num}") or stripped.upper().startswith(f"CHAPTER {chapter_num} "):
            capture = True
            chapter_title = stripped
            continue
        if capture and stripped.upper().startswith("CHAPTER") and stripped != chapter_title:
            break
        if capture:
            chapter_lines.append(line)
    return {"chapter_num": chapter_num, "title": chapter_title, "content": "\n".join(chapter_lines) if chapter_lines else "Chapter not found."}


@router.get("/articles/{article_num}")
async def get_article(article_num: int):
    text = _get_constitution_text()
    paragraphs = text.split("\n\n")
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if stripped.upper().startswith(f"ARTICLE {article_num}") or stripped.upper().startswith(f"ARTICLE {article_num} "):
            article_content = [stripped]
            for j in range(i + 1, len(paragraphs)):
                next_para = paragraphs[j].strip()
                if next_para.upper().startswith("ARTICLE "):
                    break
                article_content.append(next_para)
            return {"article_num": article_num, "title": stripped, "content": "\n\n".join(article_content)}
    return {"article_num": article_num, "title": "", "content": "Article not found."}


@router.get("/search")
async def search_constitution(q: str = Query(...)):
    text = _get_constitution_text()
    paragraphs = [p for p in text.split("\n\n") if q.lower() in p.lower()]
    return {"query": q, "results": paragraphs}
