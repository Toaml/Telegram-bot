import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from database import AsyncSessionLocal, Content


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", str(text))
    text = text.lower().strip()

    text = re.sub(r"[_\-]+", " ", text, flags=re.UNICODE)
    text = re.sub(
        r"[^\w\u0980-\u09FF]+",
        " ",
        text,
        flags=re.UNICODE
    )
    text = re.sub(r"\s+", " ", text)

    return text.strip()


REQUEST_WORDS = {
    "দাও", "দে", "দেন", "দেও", "দিয়েন", "দিবে", "দিন",
    "পাঠাও", "পাঠান", "দেখাও", "দেখান", "চাই", "চাইছি",
    "খুঁজছি", "খুঁজে", "প্লিজ", "একটা", "একটি",
    "dao", "deo", "de", "den", "din", "pathao", "pathan",
    "give", "send", "show", "please", "want", "need",
    "find", "search", "one", "ekta"
}


def clean_query(text: str) -> str:
    normalized = normalize_text(text)

    if not normalized:
        return ""

    words = normalized.split()

    return " ".join(
        word for word in words
        if word not in REQUEST_WORDS
    ).strip()


def get_words(text: str):
    normalized = normalize_text(text)

    if not normalized:
        return []

    return normalized.split()


def similarity(a: str, b: str) -> float:
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def word_overlap(a: str, b: str) -> float:
    a_words = set(get_words(a))
    b_words = set(get_words(b))

    if not a_words or not b_words:
        return 0.0

    common = a_words.intersection(b_words)

    return len(common) / max(len(a_words), len(b_words))


def token_match(query: str, target: str) -> float:
    q_words = get_words(query)
    t_words = get_words(target)

    if not q_words or not t_words:
        return 0.0

    matched = 0

    for q_word in q_words:
        for t_word in t_words:

            if q_word == t_word:
                matched += 1
                break

            if len(q_word) >= 3 and len(t_word) >= 3:
                ratio = SequenceMatcher(
                    None,
                    q_word,
                    t_word
                ).ratio()

                if ratio >= 0.82:
                    matched += 1
                    break

    return matched / len(q_words)


def score_content(query: str, item: Content) -> float:
    q = normalize_text(query)

    if not q:
        return 0.0

    title = normalize_text(item.title or "")
    category = normalize_text(item.category or "")
    keywords = normalize_text(item.keywords or "")

    if not title and not category:
        return 0.0

    if q == title:
        return 1200.0

    if q == category:
        return 1500.0

    if q in title:
        return 1100.0

    if q in category:
        return 1050.0

    if title and len(title) >= 2 and title in q:
        return 1080.0

    if category and len(category) >= 2 and category in q:
        return 1030.0

    if q == keywords:
        return 1000.0

    if q in keywords:
        return 950.0

    title_token = token_match(q, title)
    category_token = token_match(q, category)
    keyword_token = token_match(q, keywords)

    token_score = max(
        title_token * 900,
        category_token * 1000,
        keyword_token * 850
    )

    title_overlap = word_overlap(q, title)
    category_overlap = word_overlap(q, category)
    keyword_overlap = word_overlap(q, keywords)

    overlap_score = max(
        title_overlap * 850,
        category_overlap * 950,
        keyword_overlap * 800
    )

    title_similarity = similarity(q, title)
    category_similarity = similarity(q, category)
    keyword_similarity = similarity(q, keywords)

    fuzzy_score = max(
        title_similarity * 700,
        category_similarity * 800,
        keyword_similarity * 600
    )

    return max(
        token_score,
        overlap_score,
        fuzzy_score
    )


async def search_category(query: str):
    q = normalize_text(query)

    if not q:
        return None

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Content).order_by(
                Content.created_at.desc()
            )
        )

        contents = result.scalars().all()

    if not contents:
        return None

    for item in contents:
        category = normalize_text(item.category or "")

        if category and q == category:
            return item

    return None


async def search_media(query: str):
    original_query = normalize_text(query)

    if not original_query:
        return None

    cleaned_query = clean_query(original_query)

    if not cleaned_query:
        cleaned_query = original_query

    category_result = await search_category(cleaned_query)

    if category_result:
        return category_result

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Content).order_by(
                Content.created_at.desc()
            )
        )

        contents = result.scalars().all()

    if not contents:
        return None

    queries = []

    if cleaned_query:
        queries.append(cleaned_query)

    if original_query and original_query not in queries:
        queries.append(original_query)

    best_item = None
    best_score = 0.0

    for item in contents:
        item_score = 0.0

        for q in queries:
            score = score_content(q, item)

            if score > item_score:
                item_score = score

        if item_score > best_score:
            best_score = item_score
            best_item = item

    if best_item is not None:
        if best_score >= 700:
            return best_item

        if best_score >= 450:
            return best_item

    return None
