import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, delete
from config import ADMIN_IDS, ADMIN_USERNAME
from database import (
    AsyncSessionLocal, get_or_create_user, update_user_city,
    toggle_user_setting, Content, Reminder, ContentRequest, User
)
from categories import get_category_keyboard
from smart_conv import check_smart_reply
from ai_engine import get_ai_response
from search_engine import search_media
from reminder import reload_reminders
from ad_system import attach_ad_to_keyboard

# গ্লোবাল আপলোড সেশন ট্র্যাকার (রিস্টার্ট-প্রুফ ইঞ্জিন)
admin_upload_sessions = {}

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name, user.last_name)

    keyboard = [
        [InlineKeyboardButton("🤖 AI Chat", callback_data="btn_ai_help"), InlineKeyboardButton("🎬 Content", callback_data="btn_content_help")],
        [InlineKeyboardButton("⏰ Reminder", callback_data="btn_reminder_menu"), InlineKeyboardButton("🕌 Prayer Time", callback_data="btn_prayer")],
        [InlineKeyboardButton("🌦️ Weather", callback_data="btn_weather"), InlineKeyboardButton("🔔 Notifications", callback_data="btn_notifications")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="btn_help")]
    ]
    reply_markup = attach_ad_to_keyboard(InlineKeyboardMarkup(keyboard))
    welcome_text = (
        f"👋 আসসালামু আলাইকুম, {user.first_name}!\n\n"
        f"আমি আপনার অল-ইন-ওয়ান AI অ্যাসিস্ট্যান্ট।\n"
        f"যেকোনো প্রশ্ন করুন কিংবা গান/ভিডিও/নাটক খুঁজতে নাম লিখুন।\n\n"
        f"নিচের মেনু থেকেও সুবিধা বেছে নিতে পারেন: 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *বটের ব্যবহার নির্দেশিকা:*\n\n"
        "• যেকোনো প্রশ্ন বা কথা লিখলে মানুষসুলভ স্বাভাবিক উত্তর দেব।\n"
        "• নাটক বা ভিডিও পেতে লিখুন: যেমন `ব্যাচেলর পয়েন্ট ভিডিও দেও`\n"
        "• অ্যাডমিন ভিডিও/অডিও পাঠালে সরাসরি আপলোড মোড চালু হবে।"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- মিডিয়া আপলোড শুরু (Admin Only) ---
async def media_upload_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # মেমোরিতে ফাইল সেভ রাখা
    admin_upload_sessions[user_id] = {
        "step": "WAITING_TITLE",
        "file_id": file_id,
        "media_type": media_type,
        "title": ""
    }

    await message.reply_text("🎬 এই কন্টেন্টের নাম কী? সঠিক নামটি লিখে পাঠান:")

# --- বাটন ক্লিক হ্যান্ডলার (Category, Edit Name, Custom Cat, Cancel) ---
async def category_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    session = admin_upload_sessions.get(user_id)
    if not session:
        await query.message.reply_text("⚠️ এই সেশনটির মেয়াদ শেষ হয়েছে (বা বট রিস্টার্ট হয়েছিল)। অনুগ্রহ করে ভিডিও/ফাইলটি আবার পাঠান!")
        return

    # ১. নাম পরিবর্তন করুন বাটন
    if data == "admin_edit_name_btn":
        session["step"] = "WAITING_TITLE"
        await query.edit_message_text("✏️ কন্টেন্টের নতুন সঠিক নামটি লিখে পাঠান:")
        return

    # ২. কাস্টম ক্যাটাগরি বাটন
    if data == "admin_custom_cat_btn":
        session["step"] = "WAITING_CUSTOM_CAT"
        await query.edit_message_text("✍️ আপনার পছন্দের নতুন ক্যাটাগরির নাম লিখে পাঠান:")
        return

    # ৩. আপলোড বাতিল বাটন
    if data == "admin_cancel_btn":
        admin_upload_sessions.pop(user_id, None)
        await query.edit_message_text("❌ আপলোড বাতিল করা হয়েছে।")
        return

    # ৪. ক্যাটাগরি পেজিনেশন
    if data.startswith("admin_cat_page:"):
        page = int(data.split(":")[1])
        await query.edit_message_reply_markup(reply_markup=get_category_keyboard(page=page, callback_prefix="admin_cat"))
        return

    # ৫. ক্যাটাগরি নির্বাচন করে চূড়ান্ত সেভ
    if data.startswith("admin_cat:"):
        cat_name = data.split(":")[1]
        await finalize_content_save(query, user_id, cat_name)

async def finalize_content_save(event, user_id: int, category: str):
    session = admin_upload_sessions.get(user_id)
    if not session:
        return

    title = session.get("title", "Untitled")
    file_id = session.get("file_id")
    media_type = session.get("media_type")

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

    edit_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ নাম এডিট", callback_data=f"edit_cname_{cid}"),
            InlineKeyboardButton("🗑️ ডিলিট", callback_data=f"del_c_{cid}")
        ]
    ])

    success_text = (
        "✅ *Content Successfully Added!*\n\n"
        f"🎬 *Name:* {title}\n"
        f"📂 *Category:* {category}\n"
        f"💾 *Database ID:* #{cid}\n\n"
        "প্রয়োজন হলে নিচের বাটন দিয়ে সংশোধন বা ডিলিট করতে পারেন: 👇"
    )

    if hasattr(event, "edit_message_text"):
        await event.edit_message_text(success_text, reply_markup=edit_markup, parse_mode="Markdown")
    else:
        await event.reply_text(success_text, reply_markup=edit_markup, parse_mode="Markdown")

    # সেশন শেষ
    admin_upload_sessions.pop(user_id, None)

# --- সেভ করা কন্টেন্ট এডিট ও ডিলিট ---
async def edit_saved_content_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("del_c_"):
        cid = int(data.split("_")[2])
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Content).where(Content.content_id == cid))
            await session.commit()
        await query.edit_message_text(f"🗑️ কন্টেন্ট #{cid} ডাটাবেস থেকে ডিলিট করা হয়েছে।")
        return

    if data.startswith("edit_cname_"):
        cid = int(data.split("_")[2])
        admin_upload_sessions[user_id] = {
            "step": "EDITING_EXISTING_TITLE",
            "target_cid": cid
        }
        await query.message.reply_text(f"✏️ কন্টেন্ট #{cid}-এর জন্য নতুন নাম লিখে পাঠান:")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_upload_sessions:
        admin_upload_sessions.pop(user_id, None)
        await update.message.reply_text("❌ চলতি কাজ বাতিল করা হয়েছে।")
    else:
        await update.message.reply_text("বাতিল করার মতো কোনো সেশন নেই।")

# --- মূল মেসেজ হ্যান্ডলার ---
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # ১. আপলোড সেশন চেকিং (যদি অ্যাডমিন নাম লিখছেন)
    session = admin_upload_sessions.get(user_id)
    if session:
        step = session.get("step")
        if step == "WAITING_TITLE":
            session["title"] = text
            session["step"] = "SELECTING_CAT"
            keyboard = get_category_keyboard(page=0, callback_prefix="admin_cat")
            await update.message.reply_text(
                f"✅ কন্টেন্টের নাম: *{text}*\n\n📂 ক্যাটাগরি নির্বাচন করুন (ভুল হলে নিচে থেকে নাম পরিবর্তন করতে পারবেন):",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return
        elif step == "WAITING_CUSTOM_CAT":
            await finalize_content_save(update.message, user_id, text)
            return
        elif step == "EDITING_EXISTING_TITLE":
            cid = session.get("target_cid")
            async with AsyncSessionLocal() as db_sess:
                content = (await db_sess.execute(select(Content).where(Content.content_id == cid))).scalars().first()
                if content:
                    content.title = text
                    content.keywords = f"{text.lower()}, {content.category.lower()}"
                    await db_sess.commit()
                    await update.message.reply_text(f"✅ কন্টেন্ট #{cid}-এর নাম পরিবর্তন করে *{text}* করা হয়েছে!", parse_mode="Markdown")
            admin_upload_sessions.pop(user_id, None)
            return

    # ২. গ্রুপ হ্যান্ডলিং
    if chat_type in ["group", "supergroup"]:
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username
        if not (f"@{bot_username}" in text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_user.id)):
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # ৩. দ্রুত রিপ্লাই চেক
    smart_reply = check_smart_reply(text)
    if smart_reply:
        await update.message.reply_text(smart_reply)
        return

    # ৪. স্পষ্ট কন্টেন্ট সার্চ (ভিডিও/গান খোঁজা)
    t_lower = text.lower()
    ask_words = ["দাও", "দেও", "দে", "দেন", "পাঠান", "পাঠাও", "চাই", "খুঁজছি", "dao", "deo", "de", "den", "pathao", "pathan", "chai"]
    media_words = ["ভিডিও", "নাটক", "গান", "মুভি", "সিনেমা", "ওয়াজ", "video", "natok", "gan", "movie", "waz"]

    has_ask = any(w in t_lower for w in ask_words)
    has_media = any(w in t_lower for w in media_words)

    if (has_ask and has_media) or (has_media and len(text.split()) >= 2):
        wait_msg = await update.message.reply_text("অবশ্যই 😎\nএকটু অপেক্ষা করুন, দিচ্ছি..... ⏳")
        content_item = await search_media(text)

        if content_item:
            caption = f"🎬 *{content_item.title}*\n📂 ক্যাটাগরি: {content_item.category}"
            keyboard = attach_ad_to_keyboard()
            try:
                if content_item.media_type == "video":
                    await context.bot.send_video(chat_id=user_id, video=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                elif content_item.media_type == "audio":
                    await context.bot.send_audio(chat_id=user_id, audio=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                elif content_item.media_type == "photo":
                    await context.bot.send_photo(chat_id=user_id, photo=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                else:
                    await context.bot.send_document(chat_id=user_id, document=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                
                await wait_msg.delete()
                return
            except Exception:
                pass

        await wait_msg.delete()
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

        not_found_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Available Content", callback_data="btn_categories_list")],
            [InlineKeyboardButton("🔎 Search Again", callback_data="btn_search_prompt")]
        ])
        await update.message.reply_text(
            f"😔 Sorry! আপনার চাওয়া অনুযায়ী এই content এখনো আমার database-এ যোগ করা হয়নি।\n\n"
            f"আমি বিষয়টি আমার বস @{ADMIN_USERNAME}-কে জানিয়ে দিয়েছি। 👑\n"
            f"তবে আপনি চাইলে আমাদের available content দেখতে পারেন। 👇",
            reply_markup=not_found_markup
        )
        return

    # ৫. রিমাইন্ডার হ্যান্ডলার
    time_match = re.search(r"(\d{1,2})[^\d]*([০-৯]{0,2})?\s*(টায়|টা|am|pm|ঘন্টায়)", text, re.IGNORECASE)
    if ("মনে করিয়ে" in text or "রিমাইন্ডার" in text or "remind" in text.lower()) and time_match:
        hour = int(time_match.group(1))
        if any(w in text for w in ["সন্ধ্যা", "রাত", "বিকাল", "দুপুর"]) and hour < 12:
            hour += 12
        elif "সকাল" in text and hour == 12:
            hour = 0
            
        rem_type = "custom"
        if any(w in text.lower() for w in ["পড়া", "study"]): rem_type = "study"
        elif any(w in text.lower() for w in ["খেলা", "play"]): rem_type = "play"
        elif any(w in text.lower() for w in ["কাজ", "work"]): rem_type = "work"
        elif any(w in text.lower() for w in ["ঘুমা", "sleep"]): rem_type = "sleep"
        elif any(w in text.lower() for w in ["খাবার", "food"]): rem_type = "food"

        schedule_str = f"{hour:02d}:00"
        async with AsyncSessionLocal() as db_sess:
            new_rem = Reminder(user_id=user_id, reminder_type=rem_type, message=text, schedule_time=schedule_str, is_recurring=True)
            db_sess.add(new_rem)
            await db_sess.commit()
        
        await reload_reminders(context.bot)
        await update.message.reply_text(f"✅ ঠিক আছে! প্রতিদিন {schedule_str}-এ আপনাকে মনে করিয়ে দেওয়া হবে। ⏰")
        return

    # ৬. স্মার্ট এআই চ্যাট
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ai_reply = await get_ai_response(text)
    await update.message.reply_text(ai_reply)

# --- নোটিফিকেশন সেটিংস ---
async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as db_sess:
        user = (await db_sess.execute(select(User).where(User.user_id == user_id))).scalars().first()

    def get_status_icon(val):
        return "✅ ON" if val else "❌ OFF"

    keyboard = [
        [InlineKeyboardButton(f"🕌 Prayer: {get_status_icon(user.prayer_notify)}", callback_data="toggle_prayer_notify")],
        [InlineKeyboardButton(f"🕐 Hourly: {get_status_icon(user.hourly_notify)}", callback_data="toggle_hourly_notify")],
        [InlineKeyboardButton(f"📚 Study: {get_status_icon(user.study_notify)}", callback_data="toggle_study_notify")],
        [InlineKeyboardButton(f"💼 Work: {get_status_icon(user.work_notify)}", callback_data="toggle_work_notify")],
        [InlineKeyboardButton(f"😴 Sleep: {get_status_icon(user.sleep_notify)}", callback_data="toggle_sleep_notify")],
        [InlineKeyboardButton(f"🌅 Wake-up: {get_status_icon(user.wake_notify)}", callback_data="toggle_wake_notify")]
    ]
    await update.message.reply_text("⚙️ *আপনার নোটিফিকেশন সেটিংস:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def toggle_notification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field_map = {
        "toggle_prayer_notify": "prayer_notify",
        "toggle_hourly_notify": "hourly_notify",
        "toggle_study_notify": "study_notify",
        "toggle_work_notify": "work_notify",
        "toggle_sleep_notify": "sleep_notify",
        "toggle_wake_notify": "wake_notify"
    }
    field = field_map.get(query.data)
    if field:
        await toggle_user_setting(query.from_user.id, field)
        await notifications_menu(update, context)
