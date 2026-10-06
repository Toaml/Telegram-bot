import asyncio
from aiohttp import web
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from config import BOT_TOKEN, PORT
from database import init_db
from reminder import start_scheduler, reload_reminders
from handlers import (
    start_handler, help_handler, media_upload_init, media_title_received,
    category_callback_handler, cancel_conversation, handle_user_text,
    notifications_menu, toggle_notification_callback, UPLOAD_TITLE, UPLOAD_CATEGORY
)
from admin_handlers import (
    admin_panel, admin_stats, broadcast_command, view_requests
)

# Render 24/7 সচল রাখার জন্য ডামি ওয়েবসার্ভার
async def health_check(request):
    return web.Response(text="Bot is running healthy 24/7!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in environment variables!")

    # ১. ডাটাবেস টেবিল তৈরি
    await init_db()

    # ২. টেলিগ্রাম অ্যাপ্লিকেশন বিল্ডার
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ৩. মিডিয়া আপলোড কনভারসেশন হ্যান্ডলার (Admin Only)
    upload_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.VIDEO | filters.AUDIO | filters.PHOTO | filters.Document.ALL, media_upload_init)
        ],
        states={
            UPLOAD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, media_title_received)],
            UPLOAD_CATEGORY: [CallbackQueryHandler(category_callback_handler, pattern="^admin_cat")]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )

    # ৪. কমান্ড এবং হ্যান্ডলার রেজিস্টার
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("notifications", notifications_menu))
    
    application.add_handler(upload_conv)
    
    # কলব্যাক কুয়েরি হ্যান্ডলার
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(view_requests, pattern="^admin_view_requests$"))
    application.add_handler(CallbackQueryHandler(toggle_notification_callback, pattern="^toggle_"))
    
    # সাধারণ টেক্সট ও ন্যাচারাল চ্যাট হ্যান্ডলার
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))

    # ৫. রিমাইন্ডার ও ব্যাকগ্রাউন্ড শিডিউলার আরম্ভ
    start_scheduler(application.bot)
    await reload_reminders(application.bot)

    # ৬. ওয়েব হেলথ-চেক সার্ভার আরম্ভ
    await start_web_server()
    print(f"✅ Web server started on port {PORT}")

    # ৭. বট চালু করা (Polling)
    print("🚀 Telegram Bot is running asynchronously...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    # ইভেন্ট লুপ সচল রাখা
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
