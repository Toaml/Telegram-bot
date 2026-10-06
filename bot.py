import asyncio

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import BOT_TOKEN

from database import init_db

from reminder import (
    start_scheduler,
    reload_reminders
)

from handlers import (
    start_handler,
    help_handler,
    media_upload_init,
    category_callback_handler,
    edit_saved_content_callback,
    handle_user_text,
    cancel_command,
    notifications_menu,
    toggle_notification_callback,
    user_callback_handler
)

from admin_handlers import (
    admin_panel,
    admin_stats,
    broadcast_command,
    view_requests
)

from video_server import start_web_server


# =========================================================
# MAIN
# =========================================================

async def main():

    # -----------------------------------------------------
    # BOT TOKEN
    # -----------------------------------------------------

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN is not set in environment variables!"
        )


    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    await init_db()


    # -----------------------------------------------------
    # TELEGRAM APPLICATION
    # -----------------------------------------------------

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


    # =====================================================
    # COMMANDS
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start_handler
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_handler
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_panel
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            admin_stats
        )
    )

    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command
        )
    )

    application.add_handler(
        CommandHandler(
            "cancel",
            cancel_command
        )
    )

    application.add_handler(
        CommandHandler(
            "notifications",
            notifications_menu
        )
    )


    # =====================================================
    # ADMIN MEDIA UPLOAD
    # =====================================================

    application.add_handler(
        MessageHandler(
            (
                filters.VIDEO
                | filters.AUDIO
                | filters.PHOTO
                | filters.Document.ALL
            ),
            media_upload_init
        )
    )


    # =====================================================
    # ADMIN CATEGORY
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            category_callback_handler,
            pattern=(
                r"^(admin_cat"
                r"|admin_edit_name_btn"
                r"|admin_custom_cat_btn"
                r"|admin_cancel_btn)"
            )
        )
    )


    # =====================================================
    # EDIT / DELETE
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            edit_saved_content_callback,
            pattern=r"^(edit_cname_|del_c_)"
        )
    )


    # =====================================================
    # USER CALLBACK
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            user_callback_handler,
            pattern=(
                r"^(btn_"
                r"|user_categories:"
                r"|user_cat:"
                r"|user_content:)"
            )
        )
    )


    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            toggle_notification_callback,
            pattern=r"^toggle_"
        )
    )


    # =====================================================
    # ADMIN STATS CALLBACK
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            admin_stats,
            pattern=r"^admin_stats$"
        )
    )


    # =====================================================
    # ADMIN REQUESTS CALLBACK
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            view_requests,
            pattern=r"^admin_view_requests$"
        )
    )


    # =====================================================
    # NORMAL TEXT
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_user_text
        )
    )


    # =====================================================
    # REMINDER
    # =====================================================

    start_scheduler(
        application.bot
    )

    await reload_reminders(
        application.bot
    )


    # =====================================================
    # WEB SERVER
    # =====================================================

    await start_web_server()


    # =====================================================
    # START BOT
    # =====================================================

    print(
        "🚀 Telegram Bot is running asynchronously..."
    )

    await application.initialize()

    await application.start()

    await application.updater.start_polling(
        drop_pending_updates=True
    )


    # =====================================================
    # KEEP RUNNING
    # =====================================================

    await asyncio.Event().wait()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except (
        KeyboardInterrupt,
        SystemExit
    ):

        print(
            "Bot stopped."
    )
