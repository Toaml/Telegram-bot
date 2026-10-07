import re
import unicodedata

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo
)

from telegram.ext import ContextTypes

from sqlalchemy import (
    select,
    delete,
    func
)

from config import (
    ADMIN_IDS,
    ADMIN_USERNAME,
    WEBAPP_BASE_URL
)

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


# ============================================================
# ADMIN SOCIAL LINKS
# ============================================================

ADMIN_SOCIAL_LINKS = {
    "facebook": "https://www.facebook.com/share/19PVrFHGk2/",
    "tiktok": "https://www.tiktok.com/@tomalchowdhury20",
    "whatsapp": "https://wa.me/+8801311328266",
    "telegram": "https://t.me/tomalchowdhury2"
}


# ============================================================
# ADMIN UPLOAD SESSIONS
# ============================================================

admin_upload_sessions = {}


# ============================================================
# CONTENT REQUEST WORDS
# ============================================================

CONTENT_REQUEST_WORDS = {
    "দাও", "দে", "দেন", "দেও", "দিয়েন", "দিন", "পাঠাও", "পাঠান", "দেখাও", "দেখান",
    "চাই", "চাইছি", "খুঁজছি", "খুঁজে", "dao", "deo", "de", "den", "din", "pathao",
    "pathan", "give", "send", "show", "want", "need", "find", "search"
}


# ============================================================
# NORMALIZE USER QUERY
# ============================================================

def normalize_user_query(text: str):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.lower().strip()
    text = re.sub(r"[^\w\u0980-\u09FF]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# DETECT ADMIN SOCIAL REQUEST
# ============================================================

def detect_admin_social_request(text: str):
    if not text:
        return None
    q = normalize_user_query(text)
    if not q:
        return None

    words = set(q.split())
    admin_words = {"admin", "এডমিন", "অ্যাডমিন", "এডমিনের", "অ্যাডমিনের", "এডমিনকে", "অ্যাডমিনকে", "বস", "boss"}

    if not words.intersection(admin_words):
        return None

    if words.intersection({"facebook", "ফেসবুক"}):
        return "facebook"
    if words.intersection({"tiktok", "টিকটক"}) or "tik tok" in q:
        return "tiktok"
    if words.intersection({"whatsapp", "whatapp", "হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "হোয়াটসাপ", "হোয়াটসাপ"}):
        return "whatsapp"
    if words.intersection({"telegram", "টেলিগ্রাম"}):
        return "telegram"

    return None


# ============================================================
# SEND ADMIN SOCIAL LINK
# ============================================================

async def send_admin_social_link(update, context, social_type):
    link = ADMIN_SOCIAL_LINKS.get(social_type)
    if not link:
        return False

    names = {"facebook": "Facebook", "tiktok": "TikTok", "whatsapp": "WhatsApp", "telegram": "Telegram"}
    emojis = {"facebook": "📘", "tiktok": "🎵", "whatsapp": "💬", "telegram": "✈️"}

    name = names.get(social_type, "Social")
    emoji = emojis.get(social_type, "🔗")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"{emoji} Admin {name}", url=link)]])

    await update.message.reply_text(
        f"{emoji} *Admin {name}*\n\nনিচের বাটনে ক্লিক করে Admin-এর {name} প্রোফাইলে যান: 👇",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return True


# ============================================================
# CONTENT REQUEST DETECTION (STRICTER)
# ============================================================

def looks_like_content_request(text: str):
    q = normalize_user_query(text)
    if not q:
        return False

    words = set(q.split())

    content_words = {
        "ভিডিও", "video", "videos", "গান", "gan", "song", "songs", "music",
        "মুভি", "movie", "movies", "সিনেমা", "cinema", "film", "films",
        "নাটক", "natok", "drama", "telefilm", "ওয়াজ", "ওয়াজ", "waz", "waaz"
    }

    # কন্টেন্ট শব্দ এবং চাওয়া সংক্রান্ত শব্দ দুটোই থাকলে কন্টেন্ট রিকোয়েস্ট ধরবে
    has_content_word = bool(words.intersection(content_words))
    has_request_word = bool(words.intersection(CONTENT_REQUEST_WORDS))

    if has_content_word and has_request_word:
        return True

    return False


# ============================================================
# START HANDLER
# ============================================================

async def start_handler(update, context):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name, user.last_name)

    keyboard = [
        [
            InlineKeyboardButton("🤖 AI Chat", callback_data="btn_ai_help"),
            InlineKeyboardButton("🎬 Content", callback_data="btn_content_help")
        ],
        [
            InlineKeyboardButton("⏰ Reminder", callback_data="btn_reminder_menu"),
            InlineKeyboardButton("🕌 Prayer Time", callback_data="btn_prayer")
        ],
        [
            InlineKeyboardButton("🌦️ Weather", callback_data="btn_weather"),
            InlineKeyboardButton("🔔 Notifications", callback_data="btn_notifications")
        ],
        [InlineKeyboardButton("ℹ️ Help", callback_data="btn_help")]
    ]

    reply_markup = attach_ad_to_keyboard(InlineKeyboardMarkup(keyboard))

    welcome_text = (
        f"👋 আসসালামু আলাইকুম, {user.first_name}!\n\n"
        "আমি আপনার অল-ইন-ওয়ান AI অ্যাসিস্ট্যান্ট।\n"
        "যেকোনো প্রশ্ন করুন কিংবা গান/ভিডিও/নাটক খুঁজতে নাম লিখুন।\n\n"
        "নিচের মেনু থেকেও সুবিধা বেছে নিতে পারেন: 👇"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


# ============================================================
# HELP HANDLER
# ============================================================

async def help_handler(update, context):
    help_text = (
        "📖 *বটের ব্যবহার নির্দেশিকা:*\n\n"
        "• যেকোনো প্রশ্ন বা কথা লিখলে মানুষসুলভ স্বাভাবিক উত্তর দেব।\n"
        "• Content পেতে লিখুন: `গান দাও`, `মুভি দাও`, `ব্যাচেলর পয়েন্ট ভিডিও দেও`\n"
        "• Admin-এর Social ID চাইলে লিখুন:\n"
        "  `Admin Facebook দাও` | `Admin TikTok দাও` | `Admin WhatsApp দাও`\n"
        "• অ্যাডমিন ভিডিও/অডিও পাঠালে সরাসরি আপলোড মোড চালু হবে।"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ============================================================
# MEDIA UPLOAD INIT
# ============================================================

async def media_upload_init(update, context):
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

    await message.reply_text("🎬 এই কন্টেন্টের নাম কী?\nসঠিক নামটি লিখে পাঠান:")


# ============================================================
# FINALIZE CONTENT SAVE
# ============================================================

async def finalize_content_save(event, user_id: int, category: str):
    session = admin_upload_sessions.get(user_id)
    if not session:
        return

    title = session.get("title", "Untitled")
    file_id = session.get("file_id")
    media_type = session.get("media_type")

    if not file_id or not media_type:
        admin_upload_sessions.pop(user_id, None)
        error_text = "❌ Content-এর file information পাওয়া যায়নি।\n\nভিডিও/ফাইলটি আবার পাঠান।"
        try:
            if hasattr(event, "edit_message_text"):
                await event.edit_message_text(error_text)
            else:
                await event.reply_text(error_text)
        except Exception as e:
            print("❌ File information error:", repr(e))
        return

    try:
        async with AsyncSessionLocal() as db_session:
            new_content = Content(
                title=title,
                category=category,
                file_id=file_id,
                media_type=media_type,
                keywords=f"{title.lower()}, {category.lower()}",
                uploader_id=user_id
            )
            db_session.add(new_content)
            await db_session.commit()
            await db_session.refresh(new_content)
            cid = new_content.content_id

        print(f"✅ Content saved successfully: #{cid} | {title} | {category}")
    except Exception as e:
        print("❌ PostgreSQL content save error:", repr(e))
        error_text = f"❌ Content Save করা যায়নি!\n\nError: {str(e)[:500]}"
        try:
            if hasattr(event, "edit_message_text"):
                await event.edit_message_text(error_text)
            else:
                await event.reply_text(error_text)
        except Exception:
            pass
        return

    edit_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ নাম এডিট", callback_data=f"edit_cname_{cid}"),
            InlineKeyboardButton("🗑️ ডিলিট", callback_data=f"del_c_{cid}")
        ]
    ])

    success_text = f"✅ *Content Successfully Added!*\n\n🎬 *Name:* {title}\n📂 *Category:* {category}\n💾 *Database ID:* #{cid}"
    try:
        if hasattr(event, "edit_message_text"):
            await event.edit_message_text(success_text, reply_markup=edit_markup)
        else:
            await event.reply_text(success_text, reply_markup=edit_markup)
    except Exception:
        pass

    admin_upload_sessions.pop(user_id, None)


# ============================================================
# CATEGORY CALLBACK HANDLER
# ============================================================

async def category_callback_handler(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await query.answer("⛔ আপনি Admin নন।", show_alert=True)
        return

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    session = admin_upload_sessions.get(user_id)

    if not session:
        try:
            await query.message.reply_text("⚠️ এই upload session আর পাওয়া যাচ্ছে না। অনুগ্রহ করে ফাইলটি আবার পাঠান!")
        except Exception:
            pass
        return

    if data == "admin_edit_name_btn":
        session["step"] = "WAITING_TITLE"
        await query.edit_message_text("✏️ কন্টেন্টের নতুন সঠিক নামটি লিখে পাঠান:")
        return

    if data == "admin_custom_cat_btn":
        session["step"] = "WAITING_CUSTOM_CAT"
        await query.edit_message_text("✍️ আপনার পছন্দের নতুন ক্যাটাগরির নাম লিখে পাঠান:")
        return

    if data == "admin_cancel_btn":
        admin_upload_sessions.pop(user_id, None)
        await query.edit_message_text("❌ আপলোড বাতিল করা হয়েছে।")
        return

    if data.startswith("admin_cat_page:"):
        page = int(data.split(":")[1]) if ":" in data else 0
        await query.edit_message_reply_markup(
            reply_markup=get_category_keyboard(page=page, callback_prefix="admin_cat")
        )
        return

    if data.startswith("admin_cat:"):
        cat_name = data.split(":", 1)[1]
        if cat_name.strip():
            await finalize_content_save(query, user_id, cat_name.strip())
        return


# ============================================================
# EDIT / DELETE SAVED CONTENT
# ============================================================

async def edit_saved_content_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await query.message.reply_text("⛔ আপনার এই কাজ করার অনুমতি নেই।")
        return

    if data.startswith("del_c_"):
        cid = int(data.split("_")[2])
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Content).where(Content.content_id == cid))
            await session.commit()
        await query.edit_message_text(f"🗑️ কন্টেন্ট #{cid} ডিলিট করা হয়েছে।")
        return

    if data.startswith("edit_cname_"):
        cid = int(data.split("_")[2])
        admin_upload_sessions[user_id] = {"step": "EDITING_EXISTING_TITLE", "target_cid": cid}
        await query.message.reply_text(f"✏️ কন্টেন্ট #{cid}-এর নতুন নাম লিখে পাঠান:")


# ============================================================
# CANCEL COMMAND
# ============================================================

async def cancel_command(update, context):
    user_id = update.effective_user.id
    if user_id in admin_upload_sessions:
        admin_upload_sessions.pop(user_id, None)
        await update.message.reply_text("❌ চলতি কাজ বাতিল করা হয়েছে।")
    else:
        await update.message.reply_text("বাতিল করার মতো কোনো সেশন নেই।")


# ============================================================
# SEND VIDEO WEB APP
# ============================================================

async def send_video_webapp(update, context, content_item):
    user_id = update.effective_user.id
    webapp_url = f"{WEBAPP_BASE_URL}/app?content_id={content_item.content_id}"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 OPEN", web_app=WebAppInfo(url=webapp_url))]])

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔒 *Content Locked*\n\n🎬 *{content_item.title}*\n📂 ক্যাটাগরি: {content_item.category}\n\nভিডিও দেখতে নিচের *🔓 OPEN* বাটনে চাপুন।",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return True


# ============================================================
# SEND CONTENT TO USER
# ============================================================

async def send_content_to_user(update, context, content_item):
    user_id = update.effective_user.id
    caption = f"🎬 *{content_item.title}*\n📂 ক্যাটাগরি: {content_item.category}"

    try:
        if content_item.media_type == "video":
            return await send_video_webapp(update, context, content_item)

        keyboard = attach_ad_to_keyboard(InlineKeyboardMarkup([]))

        if content_item.media_type == "audio":
            await context.bot.send_audio(chat_id=user_id, audio=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
        elif content_item.media_type == "photo":
            await context.bot.send_photo(chat_id=user_id, photo=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await context.bot.send_document(chat_id=user_id, document=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")

        return True
    except Exception as e:
        print(f"❌ Content send error: {e}")
        return False


# ============================================================
# SAVE CONTENT REQUEST
# ============================================================

async def save_content_request(update, context, text):
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as db_sess:
        req = ContentRequest(user_id=user_id, username=update.effective_user.username, query=text)
        db_sess.add(req)
        await db_sess.commit()

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 *Content Request*\n\n👤 User: @{update.effective_user.username or user_id}\n🔎 Requested: `{text}`\n❌ Status: Not Found",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# GET CATEGORIES ORDERED BY LATEST CONTENT
# ============================================================

async def get_categories_ordered_by_latest():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Content.category, func.max(Content.created_at).label("latest_content"))
            .where(Content.category.is_not(None))
            .group_by(Content.category)
            .order_by(func.max(Content.created_at).desc())
        )
        return [row[0] for row in result.all() if row[0]]


# ============================================================
# SHOW AVAILABLE CONTENT
# ============================================================

async def show_available_content(update, context, page=0):
    query = update.callback_query
    try:
        categories = await get_categories_ordered_by_latest()
    except Exception as e:
        print("❌ Available category database error:", repr(e))
        await query.edit_message_text("❌ Database connection-এর সমস্যা হয়েছে।")
        return

    if not categories:
        await query.edit_message_text("📂 এখনো কোনো content database-এ যোগ করা হয়নি।")
        return

    per_page = 8
    start = page * per_page
    end = start + per_page
    current_categories = categories[start:end]

    keyboard = []
    for index, category in enumerate(current_categories):
        global_index = start + index
        keyboard.append([InlineKeyboardButton(f"📂 {category}", callback_data=f"user_cat:{global_index}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"user_categories:{page - 1}"))
    if end < len(categories):
        nav.append(InlineKeyboardButton("➡️ More", callback_data=f"user_categories:{page + 1}"))

    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔎 Search Again", callback_data="btn_search_prompt")])

    await query.edit_message_text(
        "📂 *Available Content*\n\nসর্বশেষ যোগ করা Category সবার উপরে দেখানো হচ্ছে। 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================================
# SHOW CATEGORY CONTENT
# ============================================================

async def show_category_content(update, context, category_index):
    query = update.callback_query
    try:
        categories = await get_categories_ordered_by_latest()
    except Exception:
        await query.edit_message_text("❌ Category লোড করা যাচ্ছে না।")
        return

    if category_index < 0 or category_index >= len(categories):
        await query.edit_message_text("⚠️ এই category আর পাওয়া যাচ্ছে না.")
        return

    category = categories[category_index]
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Content).where(Content.category == category).order_by(Content.created_at.desc())
        )
        contents = result.scalars().all()

    if not contents:
        await query.edit_message_text(f"😔 *{category}* category-তে কোনো content নেই.", parse_mode="Markdown")
        return

    keyboard = []
    for item in contents[:30]:
        title = item.title[:42] + "..." if len(item.title) > 45 else item.title
        keyboard.append([InlineKeyboardButton(f"🎬 {title}", callback_data=f"user_content:{item.content_id}")])

    keyboard.append([InlineKeyboardButton("📂 Back to Categories", callback_data="user_categories:0")])

    await query.edit_message_text(f"📂 *{category}*\n\nনিচের content থেকে নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ============================================================
# SEND SELECTED CONTENT
# ============================================================

async def send_selected_content(update, context, content_id):
    query = update.callback_query
    try:
        content_id = int(content_id)
    except Exception:
        await query.answer("⚠️ Content ID ভুল।", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Content).where(Content.content_id == content_id))
        content_item = result.scalars().first()

    if not content_item:
        await query.answer("এই content আর পাওয়া যাচ্ছে না।", show_alert=True)
        return

    await query.answer()
    await send_content_to_user(update, context, content_item)


# ============================================================
# USER CALLBACK HANDLER
# ============================================================

async def user_callback_handler(update, context):
    query = update.callback_query
    data = query.data

    if data == "btn_categories_list":
        await query.answer()
        await show_available_content(update, context, page=0)
        return

    if data.startswith("user_categories:"):
        await query.answer()
        page = int(data.split(":")[1]) if ":" in data else 0
        await show_available_content(update, context, page=page)
        return

    if data.startswith("user_cat:"):
        await query.answer()
        category_index = int(data.split(":")[1]) if ":" in data else 0
        await show_category_content(update, context, category_index)
        return

    if data.startswith("user_content:"):
        content_id = int(data.split(":")[1]) if ":" in data else 0
        await send_selected_content(update, context, content_id)
        return

    if data == "btn_search_prompt":
        await query.answer()
        await query.message.reply_text("🔎 যে গান, ভিডিও, মুভি, নাটক বা category খুঁজছেন তার নাম লিখুন।\n\nউদাহরণ:\n• গান দাও\n• মুভি দাও\n• ব্যাচেলর পয়েন্ট")
        return

    if data == "btn_ai_help":
        await query.answer()
        await query.message.reply_text("🤖 আমাকে যেকোনো প্রশ্ন করতে পারেন।")
        return

    if data == "btn_content_help":
        await query.answer()
        await query.message.reply_text("🎬 Content পেতে নাম লিখে বলুন।\n\nউদাহরণ:\n• গান দাও\n• মুভি দাও")
        return

    if data == "btn_help":
        await query.answer()
        await query.message.reply_text("ℹ️ Help দেখতে /help লিখুন।")
        return

    if data == "btn_notifications":
        await query.answer()
        await notifications_menu(update, context)
        return

    await query.answer()


# ============================================================
# HANDLE USER TEXT (SMART AI FIX)
# ============================================================

async def handle_user_text(update, context):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text:
        return

    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # Admin Upload Session
    session = admin_upload_sessions.get(user_id)
    if session:
        step = session.get("step")
        if step == "WAITING_TITLE":
            session["title"] = text
            session["step"] = "SELECTING_CAT"
            keyboard = get_category_keyboard(page=0, callback_prefix="admin_cat")
            await update.message.reply_text(f"✅ কন্টেন্টের নাম: *{text}*\n\n📂 ক্যাটাগরি নির্বাচন করুন:", reply_markup=keyboard, parse_mode="Markdown")
            return
        if step == "WAITING_CUSTOM_CAT":
            await finalize_content_save(update.message, user_id, text)
            return
        if step == "EDITING_EXISTING_TITLE":
            cid = session.get("target_cid")
            async with AsyncSessionLocal() as db_sess:
                result = await db_sess.execute(select(Content).where(Content.content_id == cid))
                content = result.scalars().first()
                if content:
                    content.title = text
                    content.keywords = f"{text.lower()}, {content.category.lower()}"
                    await db_sess.commit()
                    await update.message.reply_text(f"✅ কন্টেন্ট #{cid}-এর নাম পরিবর্তন করে *{text}* করা হয়েছে!", parse_mode="Markdown")
            admin_upload_sessions.pop(user_id, None)
            return

    # Group Check
    if chat_type in ["group", "supergroup"]:
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username
        mentioned = f"@{bot_username}".lower() in text.lower()
        replied_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.id == bot_user.id
        )
        if not mentioned and not replied_to_bot:
            return
        text = re.sub(rf"@{re.escape(bot_username)}", "", text, flags=re.IGNORECASE).strip()

    # Admin Social Request
    social_type = detect_admin_social_request(text)
    if social_type:
        if await send_admin_social_link(update, context, social_type):
            return

    # Smart Quick Reply
    smart_reply = check_smart_reply(text)
    if smart_reply:
        await update.message.reply_text(smart_reply)
        return

    # Reminder Detection
    time_match = re.search(r"(\d{1,2})[^\d]*([০-৯]{0,2})?\s*(টায়|টা|am|pm|ঘন্টায়)", text, re.IGNORECASE)
    if ("মনে করিয়ে" in text or "রিমাইন্ডার" in text or "remind" in text.lower()) and time_match:
        hour = int(time_match.group(1))
        if any(w in text for w in ["সন্ধ্যা", "রাত", "বিকাল", "দুপুর"]) and hour < 12:
            hour += 12
        elif "সকাল" in text and hour == 12:
            hour = 0

        rem_type = "custom"
        lower_text = text.lower()
        if "পড়া" in text or "study" in lower_text:
            rem_type = "study"
        elif "খেলা" in text or "play" in lower_text:
            rem_type = "play"
        elif "কাজ" in text or "work" in lower_text:
            rem_type = "work"
        elif "ঘুমা" in text or "sleep" in lower_text:
            rem_type = "sleep"
        elif "খাবার" in text or "food" in lower_text:
            rem_type = "food"

        schedule_str = f"{hour:02d}:00"
        async with AsyncSessionLocal() as db_sess:
            new_rem = Reminder(user_id=user_id, reminder_type=rem_type, message=text, schedule_time=schedule_str, is_recurring=True)
            db_sess.add(new_rem)
            await db_sess.commit()

        await reload_reminders(context.bot)
        await update.message.reply_text(f"✅ ঠিক আছে! প্রতিদিন {schedule_str}-এ আপনাকে মনে করিয়ে দেওয়া হবে। ⏰")
        return

    # Explicit Content Request Check
    if looks_like_content_request(text):
        content_item = await search_media(text)
        if content_item:
            wait_msg = await update.message.reply_text("অবশ্যই 😎\nএকটু অপেক্ষা করুন, দিচ্ছি..... ⏳")
            sent = await send_content_to_user(update, context, content_item)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            if sent:
                return

        await save_content_request(update, context, text)
        not_found_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Available Content", callback_data="btn_categories_list")],
            [InlineKeyboardButton("🔎 Search Again", callback_data="btn_search_prompt")]
        ])
        await update.message.reply_text(
            f"😔 Sorry! আপনার চাওয়া অনুযায়ী এই content এখনো আমার database-এ যোগ করা হয়নি।\n\nআমি বিষয়টি আমার বস @{ADMIN_USERNAME}-কে জানিয়ে দিয়েছি। 👑",
            reply_markup=not_found_markup
        )
        return

    # Normal AI Conversation (অফিশিয়াল AI ইঞ্জিন দ্বারা উত্তর দেবে)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ai_reply = await get_ai_response(text)
    await update.message.reply_text(ai_reply)


# ============================================================
# NOTIFICATIONS MENU
# ============================================================

async def notifications_menu(update, context):
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as db_sess:
        user = (await db_sess.execute(select(User).where(User.user_id == user_id))).scalars().first()

    if not user:
        user = await get_or_create_user(user_id, update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)

    def get_status_icon(val):
        return "✅ ON" if val else "❌ OFF"

    keyboard = [
        [InlineKeyboardButton(f"🕌 Prayer: {get_status_icon(user.prayer_notify)}", callback_data="toggle_prayer_notify")],
        [InlineKeyboardButton(f"🕐 Hourly: {get_status_icon(user.hourly_notify)}", callback_data="toggle_hourly_notify")],
        [InlineKeyboardButton(f"📚 Study: {get_status_icon(user.study_notify)}", callback_data="toggle_study_notify")],
        [InlineKeyboardButton(f"💼 Work: {get_status_icon(user.work_notify)}", callback_data="toggle_work_notify")],
        [InlineKeyboardButton(f"🎮 Play: {get_status_icon(user.play_notify)}", callback_data="toggle_play_notify")],
        [InlineKeyboardButton(f"😴 Sleep: {get_status_icon(user.sleep_notify)}", callback_data="toggle_sleep_notify")],
        [InlineKeyboardButton(f"🌅 Wake-up: {get_status_icon(user.wake_notify)}", callback_data="toggle_wake_notify")],
        [InlineKeyboardButton(f"🍛 Food: {get_status_icon(user.food_notify)}", callback_data="toggle_food_notify")],
        [InlineKeyboardButton(f"⚙️ Custom: {get_status_icon(user.custom_notify)}", callback_data="toggle_custom_notify")]
    ]

    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.reply_text("⚙️ *আপনার নোটিফিকেশন সেটিংস:*", reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text("⚙️ *আপনার নোটিফিকেশন সেটিংস:*", reply_markup=markup, parse_mode="Markdown")


# ============================================================
# TOGGLE NOTIFICATION
# ============================================================

async def toggle_notification_callback(update, context):
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

    field = field_map.get(query.data)
    if field:
        await toggle_user_setting(query.from_user.id, field)
        await notifications_menu(update, context)
