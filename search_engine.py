import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from database import AsyncSessionLocal, Content


# =========================================================
# TEXT NORMALIZER
# =========================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        str(text)
    )

    text = text.lower().strip()

    # punctuation বাদ দিয়ে space
    text = re.sub(
        r"[^\w\u0980-\u09FF]+",
        " ",
        text,
        flags=re.UNICODE
    )

    # একাধিক space -> একটি space
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# REQUEST / ACTION WORDS
#
# এগুলো শুধু command/request।
# এগুলো remove হবে।
#
# কিন্তু "গান", "মুভি", "Tiktok" remove হবে না।
# =========================================================

REQUEST_WORDS = {
    # বাংলা
    "দাও",
    "দে",
    "দেন",
    "দেও",
    "দিয়েন",
    "দিবে",
    "দিন",
    "পাঠাও",
    "পাঠান",
    "দেখাও",
    "দেখান",
    "চাই",
    "চাইছি",
    "খুঁজছি",
    "খুঁজে",
    "প্লিজ",
    "একটা",
    "একটি",

    # English
    "dao",
    "deo",
    "de",
    "den",
    "din",
    "pathao",
    "pathan",
    "give",
    "send",
    "show",
    "please",
    "want",
    "need",
    "find",
    "search",
    "one",
    "ekta"
}


# =========================================================
# CLEAN QUERY
# =========================================================

def clean_query(text: str) -> str:

    normalized = normalize_text(text)

    if not normalized:
        return ""

    words = normalized.split()

    cleaned = []

    for word in words:

        if word in REQUEST_WORDS:
            continue

        cleaned.append(word)

    return " ".join(cleaned).strip()


# =========================================================
# SIMILARITY
# =========================================================

def similarity(a: str, b: str) -> float:

    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# =========================================================
# WORD OVERLAP
# =========================================================

def word_overlap(a: str, b: str) -> float:

    a_words = set(
        normalize_text(a).split()
    )

    b_words = set(
        normalize_text(b).split()
    )

    if not a_words or not b_words:
        return 0.0

    common = a_words.intersection(
        b_words
    )

    return len(common) / max(
        len(a_words),
        len(b_words)
    )


# =========================================================
# SCORE CONTENT
# =========================================================

def score_content(
    query: str,
    item: Content
) -> float:

    q = normalize_text(query)

    if not q:
        return 0.0

    title = normalize_text(
        item.title or ""
    )

    category = normalize_text(
        item.category or ""
    )

    keywords = normalize_text(
        item.keywords or ""
    )

    if not title and not category:
        return 0.0

    # -----------------------------------------------------
    # EXACT TITLE
    # -----------------------------------------------------

    if q == title:
        return 1000.0

    # -----------------------------------------------------
    # EXACT CATEGORY
    # -----------------------------------------------------

    if q == category:
        return 980.0

    # -----------------------------------------------------
    # TITLE CONTAINS QUERY
    # -----------------------------------------------------

    if q in title:
        return 900.0

    # -----------------------------------------------------
    # CATEGORY CONTAINS QUERY
    # -----------------------------------------------------

    if q in category:
        return 890.0

    # -----------------------------------------------------
    # QUERY CONTAINS TITLE
    # -----------------------------------------------------

    if (
        title
        and len(title) >= 2
        and title in q
    ):
        return 880.0

    # -----------------------------------------------------
    # QUERY CONTAINS CATEGORY
    # -----------------------------------------------------

    if (
        category
        and len(category) >= 2
        and category in q
    ):
        return 870.0

    # -----------------------------------------------------
    # KEYWORDS
    # -----------------------------------------------------

    if q in keywords:
        return 850.0

    # -----------------------------------------------------
    # WORD OVERLAP
    # -----------------------------------------------------

    title_overlap = word_overlap(
        q,
        title
    )

    category_overlap = word_overlap(
        q,
        category
    )

    keyword_overlap = word_overlap(
        q,
        keywords
    )

    overlap_score = max(
        title_overlap * 800,
        category_overlap * 820,
        keyword_overlap * 780
    )

    # -----------------------------------------------------
    # FUZZY
    # -----------------------------------------------------

    title_similarity = similarity(
        q,
        title
    )

    category_similarity = similarity(
        q,
        category
    )

    fuzzy_score = max(
        title_similarity * 650,
        category_similarity * 680
    )

    return max(
        overlap_score,
        fuzzy_score
    )


# =========================================================
# SEARCH DATABASE
# =========================================================

async def search_media(query: str):

    original_query = normalize_text(
        query
    )

    if not original_query:
        return None

    # -----------------------------------------------------
    # Remove only request words
    #
    # "Tiktok দাও" -> "tiktok"
    # "গান দাও" -> "গান"
    # "মুভি দেন" -> "মুভি"
    # -----------------------------------------------------

    cleaned_query = clean_query(
        original_query
    )

    if not cleaned_query:
        cleaned_query = original_query

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content).order_by(
                Content.created_at.desc()
            )
        )

        contents = result.scalars().all()

    if not contents:
        return None

    # -----------------------------------------------------
    # QUERY VARIATIONS
    # -----------------------------------------------------

    queries = []

    if cleaned_query:
        queries.append(
            cleaned_query
        )

    if (
        original_query
        and original_query not in queries
    ):
        queries.append(
            original_query
        )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    best_item = None
    best_score = 0.0

    for item in contents:

        item_score = 0.0

        for q in queries:

            score = score_content(
                q,
                item
            )

            if score > item_score:
                item_score = score

        if item_score > best_score:

            best_score = item_score
            best_item = item

    # -----------------------------------------------------
    # STRONG MATCH
    # -----------------------------------------------------

    if best_item is not None:

        if best_score >= 700:
            return best_item

        # Fuzzy match
        if best_score >= 300:
            return best_item

    return None
