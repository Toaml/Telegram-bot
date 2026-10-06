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
    category_callback_handler, custom_category_received, edit_saved_content_callback,
    save_existing_title_edit, cancel_conversation, handle_user_text,
    UPLOAD_TITLE, UPLOAD_CATEGORY, UPLOAD_CUSTOM_CAT, EDIT_EXISTING_TITLE
)
from admin_handlers import (
    admin_panel, admin_stats, broadcast_command, view_requests
)

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

    await init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # আপলোড এবং এডিট কনভারসেশন হ্যান্ডলার
    upload_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.VIDEO | filters.AUDIO | filters.PHOTO | filters.Document.ALL, media_upload_init),
            CallbackQueryHandler(edit_saved_content_callback, pattern="^edit_cname_")
        ],
        states={
            UPLOAD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, media_title_received)],
            UPLOAD_CATEGORY: [CallbackQueryHandler(category_callback_handler, pattern="^(admin_cat|admin_edit_name_btn|admin_custom_cat_btn|admin_cancel_btn)")],
            UPLOAD_CUSTOM_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_category_received)],
            EDIT_EXISTING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_existing_title_edit)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    application.add_handler(upload_conv)
    
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(view_requests, pattern="^admin_view_requests$"))
    application.add_handler(CallbackQueryHandler(edit_saved_content_callback, pattern="^del_c_"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))

    start_scheduler(application.bot)
    await reload_reminders(application.bot)

    await start_web_server()
    print(f"✅ Web server started on port {PORT}")

    print("🚀 Telegram Bot is running asynchronously...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
