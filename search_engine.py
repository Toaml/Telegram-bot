import re
from difflib import SequenceMatcher
from sqlalchemy import select, or_
from database import AsyncSessionLocal, Content

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def clean_query(text: str) -> str:
    stop_words = ["dao", "দাও", "pathao", "পাঠাও", "video", "ভিডিও", "natok", "নাটক", "gan", "গান", "movie", "মুভি", "please", "ekta", "একটা"]
    pattern = r"\b(" + "|".join(stop_words) + r")\b"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return cleaned.strip()

async def search_media(query: str):
    cleaned = clean_query(query)
    search_term = cleaned if len(cleaned) > 1 else query.strip()

    async with AsyncSessionLocal() as session:
        # ১. ডিরেক্ট ডাটাবেস ফিল্টার
        stmt = select(Content).where(
            or_(
                Content.title.ilike(f"%{search_term}%"),
                Content.category.ilike(f"%{search_term}%"),
                Content.keywords.ilike(f"%{search_term}%")
            )
        )
        result = await session.execute(stmt)
        contents = result.scalars().all()
        if contents:
            return contents[0]

        # ২. ফাজি সার্চ (বানান ভুল থাকলে মেলাবে)
        all_contents = (await session.execute(select(Content))).scalars().all()
        best_match = None
        best_score = 0.0

        for item in all_contents:
            score = max(
                similarity(search_term, item.title),
                similarity(query, item.title),
                similarity(search_term, item.category)
            )
            if score > best_score and score >= 0.50:
                best_score = score
                best_match = item

        return best_match
