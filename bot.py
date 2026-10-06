import asyncio
import mimetypes
from urllib.parse import urlparse

from aiohttp import web, ClientSession

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import BOT_TOKEN, PORT, ADSTERRA_SMARTLINK, AD_ENABLED

from database import (
    init_db,
    AsyncSessionLocal,
    Content
)

from sqlalchemy import select

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


# =========================================================
# RENDER WEB SERVER
# =========================================================

WEBAPP_BASE_URL = "https://telegram-bot-7hr2.onrender.com"


# =========================================================
# WEB APP HTML
# =========================================================

WEBAPP_HTML = r"""
<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0,
      maximum-scale=1.0,user-scalable=no">

<title>Video Library</title>

<style>

*{
    box-sizing:border-box;
}

html,
body{
    margin:0;
    padding:0;
    width:100%;
    min-height:100%;
    background:#080808;
    color:#fff;
    font-family:Arial,sans-serif;
}

body{
    display:flex;
    justify-content:center;
    align-items:center;
    min-height:100vh;
}

.container{
    width:100%;
    max-width:900px;
    padding:15px;
    text-align:center;
}

.card{
    width:100%;
    background:#111;
    border-radius:18px;
    padding:15px;
    box-shadow:0 0 30px rgba(0,0,0,.6);
}

.title{
    font-size:20px;
    font-weight:bold;
    margin-bottom:12px;
    word-break:break-word;
}

.video-box{
    position:relative;
    width:100%;
    background:#000;
    border-radius:14px;
    overflow:hidden;
}

video{
    display:block;
    width:100%;
    max-height:70vh;
    background:#000;
}

.lock-layer{
    position:absolute;
    inset:0;
    display:flex;
    align-items:center;
    justify-content:center;
    background:rgba(0,0,0,.72);
    z-index:5;
}

.open-button{
    border:0;
    background:#fff;
    color:#111;
    font-size:22px;
    font-weight:bold;
    padding:16px 35px;
    border-radius:50px;
    cursor:pointer;
    box-shadow:0 5px 30px rgba(255,255,255,.25);
}

.open-button:active{
    transform:scale(.96);
}

.lock-text{
    position:absolute;
    top:20px;
    left:0;
    right:0;
    font-size:14px;
    opacity:.9;
}

.status{
    margin-top:12px;
    font-size:14px;
    color:#aaa;
}

.error{
    color:#ff6b6b;
}

.hidden{
    display:none !important;
}

</style>
</head>

<body>

<div class="container">

    <div class="card">

        <div id="title" class="title">
            🎬 Video
        </div>

        <div class="video-box">

            <video
                id="player"
                controls
                playsinline
                preload="metadata">
            </video>

            <div id="lockLayer" class="lock-layer">

                <div class="lock-text">
                    🔒 Video Locked
                </div>

                <button
                    id="openButton"
                    class="open-button">
                    🔓 OPEN
                </button>

            </div>

        </div>

        <div id="status" class="status">
            🔒 ভিডিও দেখতে OPEN চাপুন
        </div>

    </div>

</div>


<script>

const params = new URLSearchParams(
    window.location.search
);

const contentId =
    params.get("content_id");

const titleElement =
    document.getElementById("title");

const player =
    document.getElementById("player");

const lockLayer =
    document.getElementById("lockLayer");

const openButton =
    document.getElementById("openButton");

const statusElement =
    document.getElementById("status");


// ======================================================
// TELEGRAM WEB APP
// ======================================================

try{

    if(
        window.Telegram &&
        window.Telegram.WebApp
    ){

        window.Telegram.WebApp.ready();

        window.Telegram.WebApp.expand();
    }

}catch(e){}


// ======================================================
// LOAD VIDEO
// ======================================================

async function loadVideo(){

    if(!contentId){

        statusElement.textContent =
            "❌ Content ID পাওয়া যায়নি।";

        statusElement.classList.add(
            "error"
        );

        return;
    }

    try{

        const response =
            await fetch(
                "/api/content/" +
                encodeURIComponent(contentId)
            );

        if(!response.ok){

            throw new Error(
                "Content not found"
            );
        }

        const data =
            await response.json();

        if(data.title){

            titleElement.textContent =
                "🎬 " + data.title;

            document.title =
                data.title;
        }

        if(data.media_type !== "video"){

            statusElement.textContent =
                "⚠️ এটি ভিডিও content নয়।";

            return;
        }

        player.src =
            "/video/" +
            encodeURIComponent(contentId);

        player.load();

    }catch(error){

        console.error(error);

        statusElement.textContent =
            "❌ ভিডিও লোড করা যায়নি।";

        statusElement.classList.add(
            "error"
        );
    }
}


// ======================================================
// UNLOCK
// ======================================================

function unlockVideo(){

    lockLayer.classList.add(
        "hidden"
    );

    statusElement.textContent =
        "✅ Video Unlocked — এখন Play করুন";

    try{

        player.controls = true;

        player.play().catch(
            function(){}
        );

    }catch(e){}

}


// ======================================================
// OPEN AD
// ======================================================

openButton.addEventListener(
    "click",
    function(){

        if(!contentId){

            return;
        }

        /*
         * একই Web App origin-এর sessionStorage-এ
         * flag রাখা হচ্ছে।
         *
         * Adsterra page থেকে Back করলে এই Web App
         * আবার ফিরে এলে pageshow event-এর মাধ্যমে
         * video unlock হবে।
         */

        try{

            sessionStorage.setItem(
                "video_ad_started_" + contentId,
                "1"
            );

        }catch(e){}


        statusElement.textContent =
            "⏳ বিজ্ঞাপন খোলা হচ্ছে...";


        /*
         * সরাসরি Adsterra SmartLink user-এর
         * Telegram button-এ দেখানো হচ্ছে না।
         *
         * Render-এর /ad endpoint SmartLink-এ
         * redirect করবে।
         */

        window.location.href =
            "/ad?content_id=" +
            encodeURIComponent(contentId);
    }
);


// ======================================================
// RETURN FROM AD
// ======================================================

window.addEventListener(
    "pageshow",
    function(){

        if(!contentId){

            return;
        }

        try{

            const flag =
                sessionStorage.getItem(
                    "video_ad_started_" +
                    contentId
                );

            if(flag === "1"){

                sessionStorage.removeItem(
                    "video_ad_started_" +
                    contentId
                );

                unlockVideo();
            }

        }catch(e){}
    }
);


// ======================================================
// INIT
// ======================================================

loadVideo();

</script>

</body>
</html>
"""


# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check(request):

    return web.Response(
        text="Telegram Bot + Video Server is running!",
        status=200
    )


# =========================================================
# CONTENT API
# =========================================================

async def content_api(request):

    content_id = request.match_info.get(
        "content_id"
    )

    try:

        cid = int(content_id)

    except Exception:

        return web.json_response(
            {
                "error": "Invalid content ID"
            },
            status=400
        )

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content).where(
                Content.content_id == cid
            )
        )

        content = (
            result.scalars().first()
        )

    if not content:

        return web.json_response(
            {
                "error": "Content not found"
            },
            status=404
        )

    return web.json_response(
        {
            "content_id": content.content_id,
            "title": content.title,
            "category": content.category,
            "media_type": content.media_type
        }
    )


# =========================================================
# VIDEO STREAM
# =========================================================

async def video_stream(request):

    content_id = request.match_info.get(
        "content_id"
    )

    try:

        cid = int(content_id)

    except Exception:

        return web.Response(
            text="Invalid content ID",
            status=400
        )

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Content).where(
                Content.content_id == cid
            )
        )

        content = (
            result.scalars().first()
        )

    if not content:

        return web.Response(
            text="Video not found",
            status=404
        )

    if content.media_type != "video":

        return web.Response(
            text="This content is not a video",
            status=400
        )

    if not content.file_id:

        return web.Response(
            text="Telegram file ID missing",
            status=404
        )

    try:

        telegram_file = await application_global.bot.get_file(
            content.file_id
        )

        file_url = telegram_file.file_path

        if not file_url:

            return web.Response(
                text="Telegram file URL unavailable",
                status=404
            )

        if not file_url.startswith("http"):

            file_url = (
                "https://api.telegram.org/file/bot"
                + BOT_TOKEN
                + "/"
                + file_url
            )

        request_headers = {}

        range_header = request.headers.get(
            "Range"
        )

        if range_header:

            request_headers["Range"] = range_header


        session = ClientSession()

        try:

            upstream = await session.get(
                file_url,
                headers=request_headers
            )

        except Exception:

            await session.close()

            raise


        response_headers = {}

        content_type = upstream.headers.get(
            "Content-Type",
            "video/mp4"
        )

        response_headers["Content-Type"] = (
            content_type
        )

        if upstream.headers.get(
            "Content-Length"
        ):

            response_headers[
                "Content-Length"
            ] = upstream.headers[
                "Content-Length"
            ]

        if upstream.headers.get(
            "Content-Range"
        ):

            response_headers[
                "Content-Range"
            ] = upstream.headers[
                "Content-Range"
            ]

        response_headers[
            "Accept-Ranges"
        ] = "bytes"

        response = web.StreamResponse(
            status=upstream.status,
            headers=response_headers
        )

        await response.prepare(
            request
        )

        try:

            async for chunk in upstream.content.iter_chunked(
                1024 * 64
            ):

                await response.write(
                    chunk
                )

        except (
            asyncio.CancelledError,
            ConnectionResetError,
            BrokenPipeError
        ):

            pass

        finally:

            upstream.close()

            await session.close()

        try:

            await response.write_eof()

        except Exception:

            pass

        return response

    except Exception as e:

        print(
            f"❌ Video stream error: {e}"
        )

        return web.Response(
            text="Video streaming failed",
            status=500
        )


# =========================================================
# AD REDIRECT
# =========================================================

async def ad_redirect(request):

    content_id = request.query.get(
        "content_id",
        ""
    )

    if not AD_ENABLED:

        return web.Response(
            text="""
            <html>
            <body style="background:#111;color:white;text-align:center;padding:50px;font-family:Arial">
            <h2>Ad is disabled</h2>
            <p>Back চাপুন।</p>
            </body>
            </html>
            """,
            content_type="text/html"
        )

    if not ADSTERRA_SMARTLINK:

        return web.Response(
            text="""
            <html>
            <body style="background:#111;color:white;text-align:center;padding:50px;font-family:Arial">
            <h2>Advertisement unavailable</h2>
            <p>Back চাপুন।</p>
            </body>
            </html>
            """,
            content_type="text/html"
        )

    return web.HTTPFound(
        ADSTERRA_SMARTLINK
    )


# =========================================================
# WEB APP PAGE
# =========================================================

async def webapp_page(request):

    return web.Response(
        text=WEBAPP_HTML,
        content_type="text/html",
        charset="utf-8"
    )


# =========================================================
# WEB SERVER
# =========================================================

async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health_check
    )

    app.router.add_get(
        "/health",
        health_check
    )

    app.router.add_get(
        "/app",
        webapp_page
    )

    app.router.add_get(
        "/api/content/{content_id}",
        content_api
    )

    app.router.add_get(
        "/video/{content_id}",
        video_stream
    )

    app.router.add_get(
        "/ad",
        ad_redirect
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Web server running on port {PORT}"
    )


# =========================================================
# GLOBAL APPLICATION REFERENCE
# =========================================================

application_global = None


# =========================================================
# MAIN
# =========================================================

async def main():

    global application_global

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

    application_global = application


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
