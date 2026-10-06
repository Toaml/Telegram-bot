import asyncio

from aiohttp import web, ClientSession, ClientTimeout

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import (
    BOT_TOKEN,
    PORT,
    ADSTERRA_SMARTLINK,
    AD_ENABLED,
    WEBAPP_BASE_URL
)

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
# GLOBAL TELEGRAM APPLICATION
# =========================================================

application_global = None


# =========================================================
# WEB APP HTML
# =========================================================

WEBAPP_HTML = r"""
<!DOCTYPE html>
<html lang="bn">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,
    initial-scale=1.0,
    maximum-scale=1.0,
    user-scalable=no"
>

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
}

.card{
    width:100%;
    background:#111;
    border-radius:18px;
    padding:15px;
    box-shadow:0 0 30px rgba(0,0,0,.65);
}

.title{
    font-size:20px;
    font-weight:bold;
    margin-bottom:12px;
    text-align:center;
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
    max-height:72vh;
    background:#000;
}

.lock-layer{
    position:absolute;
    inset:0;
    display:flex;
    align-items:center;
    justify-content:center;
    background:rgba(0,0,0,.78);
    z-index:10;
}

.lock-text{
    position:absolute;
    top:20px;
    left:0;
    right:0;
    text-align:center;
    font-size:15px;
    color:#fff;
    font-weight:bold;
}

.open-button{
    border:0;
    outline:none;
    background:#fff;
    color:#111;
    font-size:22px;
    font-weight:bold;
    padding:16px 38px;
    border-radius:50px;
    cursor:pointer;
    box-shadow:0 5px 35px rgba(255,255,255,.28);
    -webkit-tap-highlight-color:transparent;
}

.open-button:active{
    transform:scale(.95);
}

.status{
    margin-top:13px;
    text-align:center;
    font-size:14px;
    color:#aaa;
}

.error{
    color:#ff6b6b;
}

.success{
    color:#72ff9b;
}

.hidden{
    display:none !important;
}

.loading{
    position:absolute;
    inset:0;
    z-index:20;
    display:none;
    align-items:center;
    justify-content:center;
    background:rgba(0,0,0,.82);
}

.loading.show{
    display:flex;
}

.loading-box{
    text-align:center;
    font-size:15px;
}

.spinner{
    width:40px;
    height:40px;
    margin:0 auto 12px;
    border:4px solid #555;
    border-top-color:#fff;
    border-radius:50%;
    animation:spin 1s linear infinite;
}

@keyframes spin{
    to{
        transform:rotate(360deg);
    }
}

</style>

</head>

<body>

<div class="container">

    <div class="card">

        <div
            id="title"
            class="title"
        >
            🎬 Video
        </div>

        <div class="video-box">

            <video
                id="player"
                controls
                playsinline
                preload="metadata"
                controlsList="nodownload"
            ></video>

            <div
                id="lockLayer"
                class="lock-layer"
            >

                <div class="lock-text">
                    🔒 Video Locked
                </div>

                <button
                    id="openButton"
                    class="open-button"
                    type="button"
                >
                    🔓 OPEN
                </button>

            </div>

            <div
                id="loading"
                class="loading"
            >

                <div class="loading-box">

                    <div class="spinner"></div>

                    <div>
                        বিজ্ঞাপন খোলা হচ্ছে...
                    </div>

                </div>

            </div>

        </div>

        <div
            id="status"
            class="status"
        >
            🔒 ভিডিও দেখতে OPEN চাপুন
        </div>

    </div>

</div>


<script>

(function(){

"use strict";


// ======================================================
// URL PARAMETERS
// ======================================================

const params =
    new URLSearchParams(
        window.location.search
    );

const contentId =
    params.get("content_id");


// ======================================================
// ELEMENTS
// ======================================================

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

const loadingElement =
    document.getElementById("loading");


// ======================================================
// STATE
// ======================================================

let adStarted = false;

let videoLoaded = false;

let videoUnlocked = false;


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

}catch(error){

    console.log(
        "Telegram WebApp error:",
        error
    );

}


// ======================================================
// STORAGE KEY
// ======================================================

function getStorageKey(){

    return (
        "video_ad_started_" +
        String(contentId || "")
    );

}


// ======================================================
// MARK AD STARTED
// ======================================================

function markAdStarted(){

    try{

        sessionStorage.setItem(
            getStorageKey(),
            "1"
        );

    }catch(error){

        console.log(
            "Session storage error:",
            error
        );

    }

}


// ======================================================
// CHECK AD FLAG
// ======================================================

function wasAdStarted(){

    try{

        return (
            sessionStorage.getItem(
                getStorageKey()
            ) === "1"
        );

    }catch(error){

        return false;

    }

}


// ======================================================
// CLEAR AD FLAG
// ======================================================

function clearAdFlag(){

    try{

        sessionStorage.removeItem(
            getStorageKey()
        );

    }catch(error){}

}


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
                encodeURIComponent(
                    contentId
                ),
                {
                    method:"GET",
                    cache:"no-store"
                }
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


        if(
            data.media_type !==
            "video"
        ){

            statusElement.textContent =
                "⚠️ এটি ভিডিও content নয়।";

            statusElement.classList.add(
                "error"
            );

            return;

        }


        player.src =
            "/video/" +
            encodeURIComponent(
                contentId
            );

        player.load();

        videoLoaded = true;


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
// UNLOCK VIDEO
// ======================================================

function unlockVideo(){

    if(videoUnlocked){

        return;

    }


    videoUnlocked = true;


    lockLayer.classList.add(
        "hidden"
    );


    loadingElement.classList.remove(
        "show"
    );


    statusElement.textContent =
        "✅ Video Unlocked — Play করুন";

    statusElement.classList.remove(
        "error"
    );

    statusElement.classList.add(
        "success"
    );


    try{

        player.controls = true;

    }catch(error){}


    try{

        const playPromise =
            player.play();

        if(
            playPromise &&
            typeof playPromise.catch ===
            "function"
        ){

            playPromise.catch(
                function(){

                    statusElement.textContent =
                        "✅ Video Unlocked — Play চাপুন";

                }
            );

        }

    }catch(error){

        statusElement.textContent =
            "✅ Video Unlocked — Play চাপুন";

    }

}


// ======================================================
// RETURN FROM AD
// ======================================================

function handleReturnFromAd(){

    if(!contentId){

        return;

    }


    if(!adStarted){

        if(!wasAdStarted()){

            return;

        }

    }


    if(!wasAdStarted()){

        return;

    }


    clearAdFlag();

    unlockVideo();

}


// ======================================================
// OPEN AD
// ======================================================

openButton.addEventListener(
    "click",
    function(){

        if(!contentId){

            statusElement.textContent =
                "❌ Content ID পাওয়া যায়নি।";

            return;

        }


        adStarted = true;


        markAdStarted();


        statusElement.textContent =
            "⏳ বিজ্ঞাপন খোলা হচ্ছে...";


        loadingElement.classList.add(
            "show"
        );


        const adUrl =
            window.location.origin +
            "/ad?content_id=" +
            encodeURIComponent(
                contentId
            );


        let opened = null;


        try{

            opened =
                window.open(
                    adUrl,
                    "_blank"
                );

        }catch(error){

            console.log(
                "window.open error:",
                error
            );

        }


        if(
            !opened &&
            window.Telegram &&
            window.Telegram.WebApp &&
            typeof window.Telegram.WebApp.openLink ===
            "function"
        ){

            try{

                window.Telegram.WebApp.openLink(
                    adUrl
                );

                opened = true;

            }catch(error){

                console.log(
                    "Telegram openLink error:",
                    error
                );

            }

        }


        if(!opened){

            loadingElement.classList.remove(
                "show"
            );

            statusElement.textContent =
                "⚠️ বিজ্ঞাপন খোলা যায়নি। "
                + "Popup permission চালু করুন।";

        }

    }
);


// ======================================================
// WINDOW FOCUS
// ======================================================

window.addEventListener(
    "focus",
    function(){

        if(!adStarted){

            return;

        }

        setTimeout(
            handleReturnFromAd,
            500
        );

    }
);


// ======================================================
// VISIBILITY CHANGE
// ======================================================

document.addEventListener(
    "visibilitychange",
    function(){

        if(
            document.visibilityState ===
            "visible"
        ){

            if(adStarted){

                setTimeout(
                    handleReturnFromAd,
                    500
                );

            }

        }

    }
);


// ======================================================
// PAGE SHOW
// ======================================================

window.addEventListener(
    "pageshow",
    function(){

        if(
            adStarted ||
            wasAdStarted()
        ){

            setTimeout(
                handleReturnFromAd,
                500
            );

        }

    }
);


// ======================================================
// PAGE HIDE
// ======================================================

window.addEventListener(
    "pagehide",
    function(){

    }
);


// ======================================================
// INIT
// ======================================================

loadVideo();


})();

</script>

</body>

</html>
"""


# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check(request):

    return web.Response(
        text=(
            "Telegram Bot + Video Web App "
            "is running!"
        ),
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

        cid = int(
            content_id
        )

    except Exception:

        return web.json_response(
            {
                "error":
                    "Invalid content ID"
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
                "error":
                    "Content not found"
            },
            status=404
        )


    return web.json_response(
        {
            "content_id":
                content.content_id,

            "title":
                content.title,

            "category":
                content.category,

            "media_type":
                content.media_type
        },
        headers={
            "Cache-Control":
                "no-store"
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

        cid = int(
            content_id
        )

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


    if not BOT_TOKEN:

        return web.Response(
            text="BOT_TOKEN missing",
            status=500
        )


    if application_global is None:

        return web.Response(
            text="Telegram application not ready",
            status=503
        )


    try:

        telegram_file = (
            await application_global.bot.get_file(
                content.file_id
            )
        )


        file_url = (
            telegram_file.file_path
        )


        if not file_url:

            return web.Response(
                text="Telegram file URL unavailable",
                status=404
            )


        if not (
            file_url.startswith("http://")
            or file_url.startswith("https://")
        ):

            file_url = (
                "https://api.telegram.org/file/bot"
                + BOT_TOKEN
                + "/"
                + file_url
            )


        request_headers = {}


        range_header = (
            request.headers.get("Range")
        )


        if range_header:

            request_headers[
                "Range"
            ] = range_header


        timeout = ClientTimeout(
            total=None,
            connect=30,
            sock_read=None
        )


        async with ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                file_url,
                headers=request_headers
            ) as upstream:

                response_headers = {}


                content_type = (
                    upstream.headers.get(
                        "Content-Type",
                        "video/mp4"
                    )
                )


                response_headers[
                    "Content-Type"
                ] = content_type


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


                response_headers[
                    "Cache-Control"
                ] = "no-store"


                response = web.StreamResponse(
                    status=upstream.status,
                    headers=response_headers
                )


                await response.prepare(
                    request
                )


                try:

                    async for chunk in (
                        upstream.content.iter_chunked(
                            64 * 1024
                        )
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


                try:

                    await response.write_eof()

                except Exception:

                    pass


                return response


    except asyncio.CancelledError:

        raise


    except Exception as e:

        print(
            "❌ Video stream error:",
            repr(e)
        )

        return web.Response(
            text="Video streaming failed",
            status=500
        )


# =========================================================
# AD REDIRECT
# =========================================================

async def ad_redirect(request):

    if not AD_ENABLED:

        return web.Response(
            text="""
<!DOCTYPE html>
<html lang="bn">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width,
initial-scale=1.0"
>

<title>Advertisement</title>

</head>

<body style="
background:#111;
color:white;
font-family:Arial;
text-align:center;
padding:60px 20px;
">

<h2>Advertisement Disabled</h2>

<p>
Back চাপুন এবং ভিডিওতে ফিরে যান।
</p>

</body>

</html>
""",
            content_type="text/html",
            charset="utf-8"
        )


    if not ADSTERRA_SMARTLINK:

        return web.Response(
            text="""
<!DOCTYPE html>
<html lang="bn">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width,
initial-scale=1.0"
>

<title>Advertisement</title>

</head>

<body style="
background:#111;
color:white;
font-family:Arial;
text-align:center;
padding:60px 20px;
">

<h2>Advertisement Unavailable</h2>

<p>
Back চাপুন এবং ভিডিওতে ফিরে যান।
</p>

</body>

</html>
""",
            content_type="text/html",
            charset="utf-8"
        )


    raise web.HTTPFound(
        ADSTERRA_SMARTLINK
    )


# =========================================================
# WEB APP PAGE
# =========================================================

async def webapp_page(request):

    return web.Response(
        text=WEBAPP_HTML,
        content_type="text/html",
        charset="utf-8",
        headers={
            "Cache-Control":
                "no-store, no-cache, must-revalidate",
            "Pragma":
                "no-cache",
            "Expires":
                "0"
        }
    )


# =========================================================
# WEB SERVER
# =========================================================

async def start_web_server():

    app = web.Application()


    # -----------------------------------------------------
    # HEALTH
    # -----------------------------------------------------

    app.router.add_get(
        "/",
        health_check
    )


    app.router.add_get(
        "/health",
        health_check
    )


    # -----------------------------------------------------
    # WEB APP
    # -----------------------------------------------------

    app.router.add_get(
        "/app",
        webapp_page
    )


    # -----------------------------------------------------
    # CONTENT API
    # -----------------------------------------------------

    app.router.add_get(
        "/api/content/{content_id}",
        content_api
    )


    # -----------------------------------------------------
    # VIDEO
    # -----------------------------------------------------

    app.router.add_get(
        "/video/{content_id}",
        video_stream
    )


    # -----------------------------------------------------
    # AD
    # -----------------------------------------------------

    app.router.add_get(
        "/ad",
        ad_redirect
    )


    # -----------------------------------------------------
    # START SERVER
    # -----------------------------------------------------

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


    print(
        "🔗 Web App:",
        WEBAPP_BASE_URL + "/app"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    global application_global


    # =====================================================
    # BOT TOKEN CHECK
    # =====================================================

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN is not set in environment variables!"
        )


    # =====================================================
    # DATABASE
    # =====================================================

    await init_db()


    # =====================================================
    # TELEGRAM APPLICATION
    # =====================================================

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
    # START TELEGRAM APPLICATION
    # =====================================================

    print(
        "🚀 Initializing Telegram Bot..."
    )

    await application.initialize()


    await application.start()


    await application.updater.start_polling(
        drop_pending_updates=True
    )


    print(
        "✅ Telegram Bot is running."
    )


    # =====================================================
    # REMINDER SCHEDULER
    # =====================================================
    #
    # IMPORTANT:
    # application.bot এখানে সরাসরি দেওয়া হবে না।
    #
    # Scheduler-কে পুরো application দেওয়া হচ্ছে।
    #
    # Telegram application initialize/start হওয়ার পরে
    # scheduler চালু করা হচ্ছে।
    #

    start_scheduler(
        application
    )


    await reload_reminders(
        application
    )


    # =====================================================
    # WEB SERVER
    # =====================================================

    await start_web_server()


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
