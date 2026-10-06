import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func, delete
from config import ADMIN_IDS
from database import AsyncSessionLocal, User, Content, Reminder, ContentRequest
from categories import get_category_keyboard

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ আপনার এই কমান্ডটি ব্যবহারের অনুমতি নেই।")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast_prompt")],
        [InlineKeyboardButton("➕ Add Content", callback_data="admin_upload_prompt"), InlineKeyboardButton("📂 Manage Content", callback_data="admin_manage_content")],
        [InlineKeyboardButton("📋 Requests", callback_data="admin_view_requests"), InlineKeyboardButton("📁 Categories", callback_data="admin_view_categories")],
        [InlineKeyboardButton("💰 Ad Settings", callback_data="admin_ad_settings")]
    ]
    await update.message.reply_text("👑 *স্বাগতম অ্যাডমিন কন্ট্রোল প্যানেলে!*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    async with AsyncSessionLocal() as session:
        total_users = (await session.execute(select(func.count(User.user_id)))).scalar() or 0
        total_contents = (await session.execute(select(func.count(Content.content_id)))).scalar() or 0
        total_reminders = (await session.execute(select(func.count(Reminder.reminder_id)))).scalar() or 0
        total_requests = (await session.execute(select(func.count(ContentRequest.request_id)))).scalar() or 0
        
        videos = (await session.execute(select(func.count(Content.content_id)).where(Content.media_type == "video"))).scalar() or 0
        audios = (await session.execute(select(func.count(Content.content_id)).where(Content.media_type == "audio"))).scalar() or 0
        photos = (await session.execute(select(func.count(Content.content_id)).where(Content.media_type == "photo"))).scalar() or 0

    stats_msg = (
        "📊 *বটের সার্বিক পরিসংখ্যান:*\n\n"
        f"👥 মোট ইউজার: *{total_users}*\n"
        f"🎬 মোট কনটেন্ট: *{total_contents}*\n"
        f"   📹 ভিডিও: {videos}\n"
        f"   🎵 অডিও: {audios}\n"
        f"   🖼️ ছবি: {photos}\n"
        f"⏰ সক্রিয় রিমাইন্ডার: *{total_reminders}*\n"
        f"📋 পেন্ডিং রিকোয়েস্ট: *{total_requests}*"
    )
    if query:
        await query.edit_message_text(stats_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(stats_msg, parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("ব্যবহার: `/broadcast আপনার মেসেজ` অথবা কোনো মেসেজে রিপ্লাই করে `/broadcast` লিখুন।", parse_mode="Markdown")
        return

    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()

    sent = 0
    failed = 0
    msg = await update.message.reply_text("⏳ ব্রডকাস্ট শুরু হচ্ছে...")

    for uid in users:
        try:
            if update.message.reply_to_message:
                await update.message.reply_to_message.copy(chat_id=uid)
            else:
                broadcast_text = " ".join(context.args)
                await context.bot.send_message(chat_id=uid, text=broadcast_text)
            sent += 1
            await asyncio.sleep(0.05)  # Telegram Rate Limit Handling
        except Exception:
            failed += 1

    await msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন!\n\nসফল: {sent}\nব্যর্থ: {failed}")

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with AsyncSessionLocal() as session:
        requests = (await session.execute(select(ContentRequest).order_by(ContentRequest.created_at.desc()).limit(10))).scalars().all()

    if not requests:
        await query.edit_message_text("✅ এই মুহূর্তে কোনো নতুন কনটেন্ট রিকোয়েস্ট নেই!")
        return

    msg = "📋 *সর্বশেষ ১০টি কন্টেন্ট রিকোয়েস্ট:*\n\n"
    for r in requests:
        user_mention = f"@{r.username}" if r.username else f"ID: {r.user_id}"
        msg += f"• 👤 {user_mention}\n  🔎 চাওয়া হয়েছে: `{r.query}`\n  📅 সময়: {r.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"

    await query.edit_message_text(msg, parse_mode="Markdown")
