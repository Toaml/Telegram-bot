from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CATEGORIES = [
    "Action", "Adventure", "Animation", "Anime", "Biography", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "History", "Horror", "Music",
    "Musical", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War",
    "Western", "Natok", "Bangla Natok", "Eid Natok", "Romantic Natok", "Comedy Natok",
    "Telefilm", "Movie Clip", "Short Film", "Web Series", "Series", "Hollywood",
    "Bollywood", "Dhallywood", "South Indian", "Korean Drama", "Turkish Drama",
    "Music Video", "Audio Song", "Bangla Song", "Hindi Song", "English Song",
    "Acoustic", "Remix", "Lofi Song", "Slowed Reverb", "Folk Song", "Rock Music",
    "Hip Hop", "Islamic", "Islamic Waz", "Islamic Song", "Quran Recitation",
    "Hadith Discussion", "Islamic Lecture", "Podcast", "Interview", "Talk Show",
    "Educational", "Tutorial", "Technology", "Programming", "Science", "Gaming",
    "Gaming Highlights", "Short Video", "Funny Video", "Viral Video", "Trending",
    "Meme Clips", "Football", "Cricket", "Sports Highlight", "Fitness", "Health",
    "Cookery", "Travel", "Vlog", "Daily Vlog", "News", "Documentary Video",
    "Kids Cartoon", "Rhymes", "Motivation", "Business", "Stock Market", "Freelancing",
    "Graphic Design", "Web Development", "AI Tools", "Life Hacks", "DIY",
    "Unboxing", "Gadget Review", "Book Summary", "Poetry", "Standup Comedy",
    "Magic Show", "Wildlife", "Space & Universe", "Celebrity News", "Fashion", "Others"
]

ITEMS_PER_PAGE = 8

def get_category_keyboard(page: int = 0, callback_prefix: str = "cat") -> InlineKeyboardMarkup:
    total_items = len(CATEGORIES)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_categories = CATEGORIES[start_idx:end_idx]

    buttons = []
    # ২ টি করে বাটন এক লাইনে
    row = []
    for cat in current_categories:
        row.append(InlineKeyboardButton(text=f"📂 {cat}", callback_data=f"{callback_prefix}:{cat}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"{callback_prefix}_page:{page - 1}"))
    if end_idx < total_items:
        nav_row.append(InlineKeyboardButton(text="➡️ See More", callback_data=f"{callback_prefix}_page:{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(buttons)
