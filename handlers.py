import re
import unicodedata

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, delete

from config import ADMIN_IDS, ADMIN_USERNAME
from database import (
    AsyncSessionLocal,
    get_or_create_user,
    update_user_city,
    toggle_user_setting,
    Content,
    Reminder,
    ContentRequest,
    User
)
from categories import get_category_keyboard
from smart_conv import check_smart_reply
from ai_engine import get_ai_response
from search_engine import search_media
from reminder import reload_reminders
from ad_system import attach_ad_to_keyboard


# =========================================================
# ADMIN SOCIAL LINKS
# =========================================================

ADMIN_SOCIAL_LINKS = {
    "facebook": "https://www.facebook.com/share/19PVrFHGk2/",
    "tiktok": "https://www.tiktok.com/@tomalchowdhury20",
    "whatsapp": "https://wa.me/+8801311328266",
    "telegram": "https://t.me/tomalchowdhury2"
}


# =========================================================
# GLOBAL ADMIN UPLOAD SESSION
# =========================================================

admin_upload_sessions = {}


# =========================================================
# TEXT HELPERS
# =========================================================

CONTENT_REQUEST_WORDS = {
    "দাও",
    "দে",
    "দেন",
    "দেও",
    "দিয়েন",
    "দিন",
    "পাঠাও",
    "পাঠান",
    "দেখাও",
    "দেখান",
    "চাই",
    "চাইছি",
    "খুঁজছি",
    "খুঁজে",
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
    "search"
}


def normalize_user_query(text: str):

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        str(text)
    )

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\u0980-\u09FF]+",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# ADMIN SOCIAL REQUEST DETECTOR
# =========================================================

def detect_admin_social_request(text: str):
    """
    শুধুমাত্র Admin-এর Social ID/Link চাওয়া হলে match করবে।

    IMPORTANT:
    শুধু TikTok/Facebook/WhatsApp/Telegram লিখলে
    Admin Social হিসেবে ধরা হবে না।

    উদাহরণ:

    Admin Tiktok
    Admin Tiktok ID দেও
    Admin Tiktok ID দাও
    Admin Tiktok deo
    এডমিনের TikTok লিংক দেন

    এগুলো Admin Social Link হিসেবে match করবে।

    কিন্তু:

    Tiktok
    Tiktok দেও
    Tiktok দাও
    Tiktok deo
    Tiktok দেন

    এগুলো database content search-এ যাবে।
    """

    if not text:
        return None

    q = normalize_user_query(text)

    if not q:
        return None

    words = set(q.split())

    # -----------------------------------------------------
    # ADMIN WORDS
    # -----------------------------------------------------

    admin_words = {
        "admin",
        "এডমিন",
        "অ্যাডমিন",
        "এডমিনের",
        "অ্যাডমিনের",
        "এডমিনকে",
        "অ্যাডমিনকে",
        "বস",
        "boss"
    }

    # -----------------------------------------------------
    # VERY IMPORTANT
    #
    # Admin শব্দ না থাকলে কখনো Social Link return করবে না।
    #
    # তাই:
    # Tiktok
    # Tiktok দাও
    # Tiktok দেও
    #
    # সব database search-এ যাবে।
    # -----------------------------------------------------

    has_admin = bool(
        words.intersection(admin_words)
    )

    if not has_admin:
        return None

    # -----------------------------------------------------
    # FACEBOOK
    # -----------------------------------------------------

    facebook_words = {
        "facebook",
        "ফেসবুক"
    }

    if words.intersection(facebook_words):
        return "facebook"

    # -----------------------------------------------------
    # TIKTOK
    # -----------------------------------------------------

    tiktok_words = {
        "tiktok",
        "টিকটক"
    }

    if (
        words.intersection(tiktok_words)
        or "tik tok" in q
    ):
        return "tiktok"

    # -----------------------------------------------------
    # WHATSAPP
    # -----------------------------------------------------

    whatsapp_words = {
        "whatsapp",
        "whatapp",
        "হোয়াটসঅ্যাপ",
        "হোয়াটসঅ্যাপ",
        "হোয়াটসাপ",
        "হোয়াটসাপ"
    }

    if words.intersection(whatsapp_words):
        return "whatsapp"

    # -----------------------------------------------------
    # TELEGRAM
    # -----------------------------------------------------

    telegram_words = {
        "telegram",
        "টেলিগ্রাম"
    }

    if words.intersection(telegram_words):
        return "telegram"

    return None


# =========================================================
# SEND ADMIN SOCIAL LINK
# =========================================================

async def send_admin_social_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    social_type: str
):

    link = ADMIN_SOCIAL_LINKS.get(
        social_type
    )

    if not link:
        return False

    names = {
        "facebook": "Facebook",
        "tiktok": "TikTok",
        "whatsapp": "WhatsApp",
        "telegram": "Telegram"
    }

    emojis = {
        "facebook": "📘",
        "tiktok": "🎵",
        "whatsapp": "💬",
        "telegram": "✈️"
    }

    name = names.get(
        social_type,
        "Social"
    )

    emoji = emojis.get(
        social_type,
        "🔗"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{emoji} Admin {name}",
                url=link
            )
        ]
    ])

    await update.message.reply_text(
        f"{emoji} *Admin {name}*\n\n"
        f"নিচের বাটনে ক্লিক করে Admin-এর {name} প্রোফাইলে যান: 👇",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return True


# =========================================================
# CONTENT REQUEST CHECK
# =========================================================

def looks_like_content_request(text: str):

    q = normalize_user_query(text)

    if not q:
        return False

    words = set(
        q.split()
    )

    if words.intersection(
        CONTENT_REQUEST_WORDS
    ):
        return True

    content_words = {
        "ভিডিও",
        "video",
        "videos",
        "গান",
        "gan",
        "song",
        "songs",
        "music",
        "মুভি",
        "movie",
        "movies",
        "সিনেমা",
        "cinema",
        "film",
        "films",
        "নাটক",
        "natok",
        "drama",
        "telefilm",
        "ওয়াজ",
        "ওয়াজ",
        "waz",
        "waaz"
    }

    if words.intersection(
        content_words
    ):
        return True

    return False


# =========================================================
# START
# =========================================================

async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    await get_or_create_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🤖 AI Chat",
                callback_data="btn_ai_help"
            ),
            InlineKeyboardButton(
                "🎬 Content",
                callback_data="btn_content_help"
            )
        ],
        [
            InlineKeyboardButton(
                "⏰ Reminder",
                callback_data="btn_reminder_menu"
            ),
            InlineKeyboardButton(
                "🕌 Prayer Time",
                callback_data="btn_prayer"
            )
        ],
        [
            InlineKeyboardButton(
                "🌦️ Weather",
                callback_data="btn_weather"
            ),
            InlineKeyboardButton(
                "🔔 Notifications",
                callback_data="btn_notifications"
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="btn_help"
            )
        ]
    ]

    reply_markup = attach_ad_to_keyboard(
        InlineKeyboardMarkup(
            keyboard
        )
    )

    welcome_text = (
        f"👋 আসসালামু আলাইকুম, {user.first_name}!\n\n"
        "আমি আপনার অল-ইন-ওয়ান AI অ্যাসিস্ট্যান্ট।\n"
        "যেকোনো প্রশ্ন করুন কিংবা গান/ভিডিও/নাটক "
        "খুঁজতে নাম লিখুন।\n\n"
        "নিচের মেনু থেকেও সুবিধা বেছে নিতে পারেন: 👇"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )


# =========================================================
# HELP
# =========================================================

async def help_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    help_text = (
        "📖 *বটের ব্যবহার নির্দেশিকা:*\n\n"
        "• যেকোনো প্রশ্ন বা কথা লিখলে মানুষসুলভ স্বাভাবিক উত্তর দেব।\n"
        "• Content পেতে শুধু নাম লিখলেও হবে।\n"
        "• যেমন: `Tiktok`\n"
        "• `গান`\n"
        "• `মুভি দাও`\n"
        "• `ব্যাচেলর পয়েন্ট ভিডিও দেও`\n"
        "• Admin-এর Social ID চাইলে লিখুন:\n"
        "  `Admin Facebook দাও`\n"
        "  `Admin TikTok দাও`\n"
        "  `Admin WhatsApp দাও`\n"
        "  `Admin Telegram দাও`\n"
        "• অ্যাডমিন ভিডিও/অডিও পাঠালে সরাসরি আপলোড মোড চালু হবে।"
    )

    await update.message.reply_text(
        help_text,
        parse_mode="Markdown"
    )


# =========================================================
# ADMIN MEDIA UPLOAD
# =========================================================

async def media_upload_init(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        return

    message = update.message

    file_id = None
    media_type = None

    if message.video:

        file_id = message.video.file_id
        media_type = "video"

    elif message.audio:

        file_id = message.audio.file_id
        media_type = "audio"

    elif message.photo:

        file_id = message.photo[-1].file_id
        media_type = "photo"

    elif message.document:

        file_id = message.document.file_id
        media_type = "document"

    if not file_id:
        return

    admin_upload_sessions[user_id] = {
        "step": "WAITING_TITLE",
        "file_id": file_id,
        "media_type": media_type,
        "title": ""
    }

    await message.reply_text(
        "🎬 এই কন্টেন্টের নাম কী?\n"
        "সঠিক নামটি লিখে পাঠান:"
    )


# =========================================================
# ADMIN CATEGORY CALLBACK
# =========================================================

async def category_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id
    data = query.data

    session = admin_upload_sessions.get(
        user_id
    )

    if not session:

        await query.message.reply_text(
            "⚠️ এই সেশনটির মেয়াদ শেষ হয়েছে "
            "(বা বট রিস্টার্ট হয়েছিল)।\n\n"
            "অনুগ্রহ করে ভিডিও/ফাইলটি আবার পাঠান!"
        )

        return

    if data == "admin_edit_name_btn":

        session["step"] = "WAITING_TITLE"

        await query.edit_message_text(
            "✏️ কন্টেন্টের নতুন সঠিক নামটি "
            "লিখে পাঠান:"
        )

        return

    if data == "admin_custom_cat_btn":

        session["step"] = "WAITING_CUSTOM_CAT"

        await query.edit_message_text(
            "✍️ আপনার পছন্দের নতুন ক্যাটাগরির "
            "নাম লিখে পাঠান:"
        )

        return

    if data == "admin_cancel_btn":

        admin_upload_sessions.pop(
            user_id,
            None
        )

        await query.edit_message_text(
            "❌ আপলোড বাতিল করা হয়েছে।"
        )

        return

    if data.startswith(
        "admin_cat_page:"
    ):

        try:

            page = int(
                data.split(":")[1]
            )

        except Exception:

            page = 0

        await query.edit_message_reply_markup(
            reply_markup=get_category_keyboard(
                page=page,
                callback_prefix="admin_cat"
            )
        )

        return

    if data.startswith(
        "admin_cat:"
    ):

        cat_name = data.split(
            ":",
            1
        )[1]

        await finalize_content_save(
            query,
            user_id,
            cat_name
        )

        return


# =========================================================
# FINALIZE CONTENT SAVE
# =========================================================

async def finalize_content_save(
    event,
    user_id: int,
    category: str
):

    session = admin_upload_sessions.get(
        user_id
    )

    if not session:
        return

    title = session.get(
        "title",
        "Untitled"
    )

    file_id = session.get(
        "file_id"
    )

    media_type = session.get(
        "media_type"
    )

    async with AsyncSessionLocal() as db_session:

        new_content = Content(
            title=title,
            category=category,
            file_id=file_id,
            media_type=media_type,
            keywords=(
                f"{title.lower()}, "
                f"{category.lower()}"
            ),
            uploader_id=user_id
        )

        db_session.add(
            new_content
        )

        await db_session.commit()

        await db_session.refresh(
            new_content
        )

        cid = new_content.content_id

    edit_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✏️ নাম এডিট",
                callback_data=f"edit_cname_{cid}"
            ),
            InlineKeyboardButton(
                "🗑️ ডিলিট",
                callback_data=f"del_c_{cid}"
            )
        ]
    ])

    success_text = (
        "✅ *Content Successfully Added!*\n\n"
        f"🎬 *Name:* {title}\n"
        f"📂 *Category:* {category}\n"
        f"💾 *Database ID:* #{cid}\n\n"
        "প্রয়োজন হলে নিচের বাটন দিয়ে "
        "সংশোধন বা ডিলিট করতে পারেন: 👇"
    )

    if hasattr(
        event,
        "edit_message_text"
    ):

        await event.edit_message_text(
            success_text,
            reply_markup=edit_markup,
            parse_mode="Markdown"
        )

    else:

        await event.reply_text(
            success_text,
            reply_markup=edit_markup,
            parse_mode="Markdown"
        )

    admin_upload_sessions.pop(
        user_id,
        None
    )


# =========================================================
# EDIT / DELETE SAVED CONTENT
# =========================================================

async def edit_saved_content_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data.startswith(
        "del_c_"
    ):

        try:

            cid = int(
                data.split("_")[2]
            )

        except Exception:

            await query.message.reply_text(
                "⚠️ Content ID ভুল।"
            )

            return

        async with AsyncSessionLocal() as session:

            await session.execute(
                delete(Content).where(
                    Content.content_id == cid
                )
            )

            await session.commit()

        await query.edit_message_text(
            f"🗑️ কন্টেন্ট #{cid} "
            "ডাটাবেস থেকে ডিলিট করা হয়েছে।"
        )

        return

    if data.startswith(
        "edit_cname_"
    ):

        try:

            cid = int(
                data.split("_")[2]
            )

        except Exception:

            await query.message.reply_text(
                "⚠️ Content ID ভুল।"
            )

            return

        admin_upload_sessions[user_id] = {
            "step": "EDITING_EXISTING_TITLE",
            "target_cid": cid
        }

        await query.message.reply_text(
            f"✏️ কন্টেন্ট #{cid}-এর জন্য "
            "নতুন নাম লিখে পাঠান:"
        )


# =========================================================
# CANCEL COMMAND
# =========================================================

async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id in admin_upload_sessions:

        admin_upload_sessions.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            "❌ চলতি কাজ বাতিল করা হয়েছে।"
        )

    else:

        await update.message.reply_text(
            "বাতিল করার মতো কোনো সেশন নেই।"
        )


# =========================================================
# SEND CONTENT
# =========================================================

async def send_content_to_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    content_item
):

    user_id = update.effective_user.id

    caption = (
        f"🎬 *{content_item.title}*\n"
        f"📂 ক্যাটাগরি: {content_item.category}"
    )

    try:

        keyboard = attach_ad_to_keyboard(
            InlineKeyboardMarkup([])
        )

        if content_item.media_type == "video":

            await context.bot.send_video(
                chat_id=user_id,
                video=content_item.file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        elif content_item.media_type == "audio":

            await context.bot.send_audio(
                chat_id=user_id,
                audio=content_item.file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        elif content_item.media_type == "photo":

            await context.bot.send_photo(
                chat_id=user_id,
                photo=content_item.file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        else:

            await context.bot.send_document(
                chat_id=user_id,
                document=content_item.file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        return True

    except Exception as e:

        print(
            f"❌ Content send error: {e}"
        )

        return False


# =========================================================
# SAVE CONTENT REQUEST
# =========================================================

async def save_content_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str
):

    user_id = update.effective_user.id

    async with AsyncSessionLocal() as db_sess:

        req = ContentRequest(
            user_id=user_id,
            username=update.effective_user.username,
            query=text
        )

        db_sess.add(
            req
        )

        await db_sess.commit()

    for admin_id in ADMIN_IDS:

        try:

            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    "🔔 *Content Request*\n\n"
                    f"👤 User: @{update.effective_user.username or user_id}\n"
                    f"🔎 Requested: `{text}`\n"
                    "❌ Status: Not Found"
                ),
                parse_mode="Markdown"
            )

        except Exception:
            pass


# =========================================================
# AVAILABLE CONTENT
# =========================================================

async def show_available_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0
):

    query = update.callback_query

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content.category)
            .where(
                Content.category.is_not(None)
            )
            .distinct()
            .order_by(
                Content.category
            )
        )

        categories = [
            row[0]
            for row in result.all()
            if row[0]
        ]

    if not categories:

        await query.edit_message_text(
            "📂 এখনো কোনো content "
            "database-এ যোগ করা হয়নি।"
        )

        return

    per_page = 8

    start = page * per_page
    end = start + per_page

    current_categories = categories[
        start:end
    ]

    keyboard = []

    for index, category in enumerate(
        current_categories
    ):

        global_index = start + index

        keyboard.append([
            InlineKeyboardButton(
                f"📂 {category}",
                callback_data=(
                    f"user_cat:{global_index}"
                )
            )
        ])

    nav = []

    if page > 0:

        nav.append(
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data=(
                    f"user_categories:{page - 1}"
                )
            )
        )

    if end < len(categories):

        nav.append(
            InlineKeyboardButton(
                "➡️ More",
                callback_data=(
                    f"user_categories:{page + 1}"
                )
            )
        )

    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton(
            "🔎 Search Again",
            callback_data="btn_search_prompt"
        )
    ])

    await query.edit_message_text(
        "📂 *Available Content*\n\n"
        "আপনার প্রয়োজনীয় ক্যাটাগরি নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown"
    )


# =========================================================
# SHOW CATEGORY CONTENT
# =========================================================

async def show_category_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    category_index: int
):

    query = update.callback_query

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content.category)
            .where(
                Content.category.is_not(None)
            )
            .distinct()
            .order_by(
                Content.category
            )
        )

        categories = [
            row[0]
            for row in result.all()
            if row[0]
        ]

        if (
            category_index < 0
            or category_index >= len(categories)
        ):

            await query.edit_message_text(
                "⚠️ এই category আর পাওয়া যাচ্ছে না।"
            )

            return

        category = categories[
            category_index
        ]

        result = await session.execute(
            select(Content)
            .where(
                Content.category == category
            )
            .order_by(
                Content.created_at.desc()
            )
        )

        contents = result.scalars().all()

    if not contents:

        await query.edit_message_text(
            f"😔 *{category}* category-তে "
            "কোনো content নেই।",
            parse_mode="Markdown"
        )

        return

    keyboard = []

    for item in contents[:30]:

        title = item.title

        if len(title) > 45:

            title = title[:42] + "..."

        keyboard.append([
            InlineKeyboardButton(
                f"🎬 {title}",
                callback_data=(
                    f"user_content:{item.content_id}"
                )
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "📂 Back to Categories",
            callback_data="user_categories:0"
        )
    ])

    await query.edit_message_text(
        f"📂 *{category}*\n\n"
        "নিচের content থেকে নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown"
    )


# =========================================================
# SEND SELECTED CONTENT
# =========================================================

async def send_selected_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    content_id: int
):

    query = update.callback_query

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content).where(
                Content.content_id == content_id
            )
        )

        content_item = (
            result.scalars().first()
        )

    if not content_item:

        await query.answer(
            "এই content আর পাওয়া যাচ্ছে না।",
            show_alert=True
        )

        return

    await query.answer()

    caption = (
        f"🎬 *{content_item.title}*\n"
        f"📂 ক্যাটাগরি: {content_item.category}"
    )

    try:

        if content_item.media_type == "video":

            await context.bot.send_video(
                chat_id=query.from_user.id,
                video=content_item.file_id,
                caption=caption,
                parse_mode="Markdown"
            )

        elif content_item.media_type == "audio":

            await context.bot.send_audio(
                chat_id=query.from_user.id,
                audio=content_item.file_id,
                caption=caption,
                parse_mode="Markdown"
            )

        elif content_item.media_type == "photo":

            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=content_item.file_id,
                caption=caption,
                parse_mode="Markdown"
            )

        else:

            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=content_item.file_id,
                caption=caption,
                parse_mode="Markdown"
            )

    except Exception as e:

        print(
            f"❌ Selected content send error: {e}"
        )

        await query.message.reply_text(
            "❌ Content পাঠানো যায়নি।"
        )


# =========================================================
# USER CALLBACK HANDLER
# =========================================================

async def user_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    data = query.data

    if data == "btn_categories_list":

        await query.answer()

        await show_available_content(
            update,
            context,
            page=0
        )

        return

    if data.startswith(
        "user_categories:"
    ):

        await query.answer()

        try:

            page = int(
                data.split(":")[1]
            )

        except Exception:

            page = 0

        await show_available_content(
            update,
            context,
            page=page
        )

        return

    if data.startswith(
        "user_cat:"
    ):

        await query.answer()

        try:

            category_index = int(
                data.split(":")[1]
            )

        except Exception:

            await query.message.reply_text(
                "⚠️ Category পাওয়া যায়নি।"
            )

            return

        await show_category_content(
            update,
            context,
            category_index
        )

        return

    if data.startswith(
        "user_content:"
    ):

        try:

            content_id = int(
                data.split(":")[1]
            )

        except Exception:

            await query.answer(
                "⚠️ Content ID ভুল।",
                show_alert=True
            )

            return

        await send_selected_content(
            update,
            context,
            content_id
        )

        return

    if data == "btn_search_prompt":

        await query.answer()

        await query.message.reply_text(
            "🔎 যে গান, ভিডিও, মুভি, নাটক "
            "বা category খুঁজছেন তার নাম লিখুন।\n\n"
            "উদাহরণ:\n"
            "• Tiktok\n"
            "• গান\n"
            "• মুভি দাও\n"
            "• ব্যাচেলর পয়েন্ট\n"
            "• Funny Video"
        )

        return

    if data == "btn_ai_help":

        await query.answer()

        await query.message.reply_text(
            "🤖 আমাকে যেকোনো প্রশ্ন করতে পারেন।"
        )

        return

    if data == "btn_content_help":

        await query.answer()

        await query.message.reply_text(
            "🎬 Content পেতে শুধু নাম লিখুন।\n\n"
            "উদাহরণ:\n"
            "Tiktok\n"
            "গান\n"
            "মুভি\n"
            "নাটক\n"
            "Funny Video"
        )

        return

    if data == "btn_help":

        await query.answer()

        await query.message.reply_text(
            "ℹ️ Help দেখতে /help লিখুন।"
        )

        return

    if data == "btn_notifications":

        await query.answer()

        await notifications_menu(
            update,
            context
        )

        return

    await query.answer()


# =========================================================
# MAIN USER TEXT HANDLER
# =========================================================

async def handle_user_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if (
        not update.message
        or not update.message.text
    ):
        return

    text = update.message.text.strip()

    if not text:
        return

    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # =====================================================
    # ADMIN UPLOAD SESSION
    # =====================================================

    session = admin_upload_sessions.get(
        user_id
    )

    if session:

        step = session.get(
            "step"
        )

        if step == "WAITING_TITLE":

            session["title"] = text
            session["step"] = "SELECTING_CAT"

            keyboard = get_category_keyboard(
                page=0,
                callback_prefix="admin_cat"
            )

            await update.message.reply_text(
                f"✅ কন্টেন্টের নাম: *{text}*\n\n"
                "📂 ক্যাটাগরি নির্বাচন করুন "
                "(ভুল হলে নিচে থেকে নাম পরিবর্তন করতে পারবেন):",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            return

        elif step == "WAITING_CUSTOM_CAT":

            await finalize_content_save(
                update.message,
                user_id,
                text
            )

            return

        elif step == "EDITING_EXISTING_TITLE":

            cid = session.get(
                "target_cid"
            )

            async with AsyncSessionLocal() as db_sess:

                content = (
                    await db_sess.execute(
                        select(Content).where(
                            Content.content_id == cid
                        )
                    )
                ).scalars().first()

                if content:

                    content.title = text

                    content.keywords = (
                        f"{text.lower()}, "
                        f"{content.category.lower()}"
                    )

                    await db_sess.commit()

                    await update.message.reply_text(
                        f"✅ কন্টেন্ট #{cid}-এর নাম পরিবর্তন "
                        f"করে *{text}* করা হয়েছে!",
                        parse_mode="Markdown"
                    )

            admin_upload_sessions.pop(
                user_id,
                None
            )

            return

    # =====================================================
    # GROUP HANDLING
    # =====================================================

    if chat_type in [
        "group",
        "supergroup"
    ]:

        bot_user = await context.bot.get_me()

        bot_username = bot_user.username

        mentioned = (
            f"@{bot_username}".lower()
            in text.lower()
        )

        replied_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.id
            == bot_user.id
        )

        if not mentioned and not replied_to_bot:
            return

        text = re.sub(
            rf"@{re.escape(bot_username)}",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        if not text:
            return

    # =====================================================
    # ADMIN SOCIAL LINK
    #
    # IMPORTANT:
    # detect_admin_social_request()
    # এখন শুধুমাত্র Admin/এডমিন/বস শব্দ থাকলে
    # Social request হিসেবে match করবে।
    #
    # তাই:
    #
    # Tiktok
    # Tiktok দেও
    # Tiktok দাও
    # Tiktok deo
    # Tiktok দেন
    #
    # database search-এ যাবে।
    # =====================================================

    social_type = detect_admin_social_request(
        text
    )

    if social_type:

        sent_social = await send_admin_social_link(
            update,
            context,
            social_type
        )

        if sent_social:
            return

    # =====================================================
    # UNIVERSAL DATABASE CONTENT SEARCH
    # =====================================================

    content_item = await search_media(
        text
    )

    if content_item:

        wait_msg = await update.message.reply_text(
            "অবশ্যই 😎\n"
            "একটু অপেক্ষা করুন, দিচ্ছি..... ⏳"
        )

        sent = await send_content_to_user(
            update,
            context,
            content_item
        )

        try:

            await wait_msg.delete()

        except Exception:
            pass

        if sent:
            return

    # =====================================================
    # CONTENT NOT FOUND
    # =====================================================

    if looks_like_content_request(
        text
    ):

        await save_content_request(
            update,
            context,
            text
        )

        not_found_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📂 Available Content",
                    callback_data="btn_categories_list"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔎 Search Again",
                    callback_data="btn_search_prompt"
                )
            ]
        ])

        await update.message.reply_text(
            "😔 Sorry! আপনার চাওয়া অনুযায়ী এই "
            "content এখনো আমার database-এ যোগ করা হয়নি।\n\n"
            f"আমি বিষয়টি আমার বস @{ADMIN_USERNAME}-কে "
            "জানিয়ে দিয়েছি। 👑\n\n"
            "তবে আপনি চাইলে আমাদের available "
            "content দেখতে পারেন। 👇",
            reply_markup=not_found_markup
        )

        return

    # =====================================================
    # SMART REPLY
    # =====================================================

    smart_reply = check_smart_reply(
        text
    )

    if smart_reply:

        await update.message.reply_text(
            smart_reply
        )

        return

    # =====================================================
    # REMINDER
    # =====================================================

    time_match = re.search(
        r"(\d{1,2})[^\d]*"
        r"([০-৯]{0,2})?\s*"
        r"(টায়|টা|am|pm|ঘন্টায়)",
        text,
        re.IGNORECASE
    )

    if (
        (
            "মনে করিয়ে" in text
            or "রিমাইন্ডার" in text
            or "remind" in text.lower()
        )
        and time_match
    ):

        hour = int(
            time_match.group(1)
        )

        if (
            any(
                w in text
                for w in [
                    "সন্ধ্যা",
                    "রাত",
                    "বিকাল",
                    "দুপুর"
                ]
            )
            and hour < 12
        ):

            hour += 12

        elif (
            "সকাল" in text
            and hour == 12
        ):

            hour = 0

        rem_type = "custom"

        lower_text = text.lower()

        if (
            "পড়া" in text
            or "study" in lower_text
        ):

            rem_type = "study"

        elif (
            "খেলা" in text
            or "play" in lower_text
        ):

            rem_type = "play"

        elif (
            "কাজ" in text
            or "work" in lower_text
        ):

            rem_type = "work"

        elif (
            "ঘুমা" in text
            or "sleep" in lower_text
        ):

            rem_type = "sleep"

        elif (
            "খাবার" in text
            or "food" in lower_text
        ):

            rem_type = "food"

        schedule_str = f"{hour:02d}:00"

        async with AsyncSessionLocal() as db_sess:

            new_rem = Reminder(
                user_id=user_id,
                reminder_type=rem_type,
                message=text,
                schedule_time=schedule_str,
                is_recurring=True
            )

            db_sess.add(
                new_rem
            )

            await db_sess.commit()

        await reload_reminders(
            context.bot
        )

        await update.message.reply_text(
            f"✅ ঠিক আছে! প্রতিদিন "
            f"{schedule_str}-এ আপনাকে মনে করিয়ে "
            "দেওয়া হবে। ⏰"
        )

        return

    # =====================================================
    # AI FALLBACK
    # =====================================================

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    ai_reply = await get_ai_response(
        text
    )

    await update.message.reply_text(
        ai_reply
    )


# =========================================================
# NOTIFICATION MENU
# =========================================================

async def notifications_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    async with AsyncSessionLocal() as db_sess:

        user = (
            await db_sess.execute(
                select(User).where(
                    User.user_id == user_id
                )
            )
        ).scalars().first()

    if not user:

        user = await get_or_create_user(
            user_id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name
        )

    def get_status_icon(val):

        return (
            "✅ ON"
            if val
            else "❌ OFF"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                f"🕌 Prayer: "
                f"{get_status_icon(user.prayer_notify)}",
                callback_data="toggle_prayer_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"🕐 Hourly: "
                f"{get_status_icon(user.hourly_notify)}",
                callback_data="toggle_hourly_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"📚 Study: "
                f"{get_status_icon(user.study_notify)}",
                callback_data="toggle_study_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"💼 Work: "
                f"{get_status_icon(user.work_notify)}",
                callback_data="toggle_work_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"🎮 Play: "
                f"{get_status_icon(user.play_notify)}",
                callback_data="toggle_play_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"😴 Sleep: "
                f"{get_status_icon(user.sleep_notify)}",
                callback_data="toggle_sleep_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"🌅 Wake-up: "
                f"{get_status_icon(user.wake_notify)}",
                callback_data="toggle_wake_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"🍛 Food: "
                f"{get_status_icon(user.food_notify)}",
                callback_data="toggle_food_notify"
            )
        ],
        [
            InlineKeyboardButton(
                f"⚙️ Custom: "
                f"{get_status_icon(user.custom_notify)}",
                callback_data="toggle_custom_notify"
            )
        ]
    ]

    if update.callback_query:

        await update.callback_query.message.reply_text(
            "⚙️ *আপনার নোটিফিকেশন সেটিংস:*",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown"
        )

    else:

        await update.message.reply_text(
            "⚙️ *আপনার নোটিফিকেশন সেটিংস:*",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown"
        )


# =========================================================
# NOTIFICATION TOGGLE
# =========================================================

async def toggle_notification_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    field_map = {
        "toggle_prayer_notify": "prayer_notify",
        "toggle_hourly_notify": "hourly_notify",
        "toggle_study_notify": "study_notify",
        "toggle_work_notify": "work_notify",
        "toggle_play_notify": "play_notify",
        "toggle_sleep_notify": "sleep_notify",
        "toggle_wake_notify": "wake_notify",
        "toggle_food_notify": "food_notify",
        "toggle_custom_notify": "custom_notify"
    }

    field = field_map.get(
        query.data
    )

    if field:

        await toggle_user_setting(
            query.from_user.id,
            field
        )

        await notifications_menu(
            update,
            context
)
