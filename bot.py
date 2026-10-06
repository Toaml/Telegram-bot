import asyncio
import html

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
// URL
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
// CHECK AD STARTED
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


        player.addEventListener(
            "error",
            function(){

                statusElement.textContent =
                    "❌ ভিডিও লোড করা যায়নি।";

                statusElement.classList.add(
                    "error"
                );

            }
        );


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
        "✅ Video Unlocked";

    statusElement.classList.remove(
        "error"
    );

    statusElement.classList.add(
        "success"
    );


    try{

        player.controls = true;

    }catch(error){}


    /*
     * Mobile browser autoplay policy অনুযায়ী
     * play() block হতে পারে।
     *
     * সেক্ষেত্রে controls থাকবে এবং user
     * Play চাপতে পারবে।
     */

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

        /*
         * Web App নতুন করে load হলে
         * session flag থেকেও বুঝতে চেষ্টা করি।
         */

        if(!wasAdStarted()){

            return;

        }

    }


    if(!wasAdStarted()){

        return;

    }


    /*
     * এখানে মূল FIX:
     *
     * Ad একই Web App-এর জায়গা নেয় না।
     * Ad নতুন tab/window-এ খোলা হয়েছে।
     *
     * User আবার এই Web App-এ ফিরে এলে
     * focus/visibility/pageshow থেকে
     * video unlock হবে।
     */

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

            return;

        }


        adStarted = true;

        markAdStarted();


        statusElement.textContent =
            "⏳ বিজ্ঞাপন খোলা হচ্ছে...";


        loadingElement.classList.add(
            "show"
        );


        /*
         * =================================================
         * IMPORTANT FIX
         * =================================================
         *
         * আগের code ছিল:
         *
         * window.location.href = "/ad";
         *
         * এতে বর্তমান Web App page replace হয়ে
         * যেত।
         *
         * এখন নতুন tab/window ব্যবহার করা হচ্ছে।
         * ফলে মূল Web App page খোলা থাকবে।
         */


        const adUrl =
            "/ad?content_id=" +
            encodeURIComponent(
                contentId
            );


        let opened = null;


        try{

            opened =
                window.open(
                    adUrl,
                    "_blank",
                    "noopener,noreferrer"
                );

        }catch(error){

            console.log(
                "window.open error:",
                error
            );

        }


        /*
         * Telegram WebView-এ window.open
         * কখনো null return করতে পারে,
         * যদিও নতুন page খুলে গেছে।
         *
         * তাই একই page-এ location.href
         * fallback করা হচ্ছে না।
         *
         * কারণ সেটাই Mobile Back সমস্যার
         * মূল কারণ ছিল।
         */


        if(!opened){

            loadingElement.classList.remove(
                "show"
            );

            statusElement.textContent =
                "⚠️ বিজ্ঞাপনটি নতুন পেজে খুলুন। "
                + "Browser popup বন্ধ থাকলে "
                + "অনুমতি দিন।";

        }

    }
);


// ======================================================
// FOCUS
// ======================================================

window.addEventListener(
    "focus",
    function(){

        setTimeout(
            handleReturnFromAd,
            300
        );

    }
);


// ======================================================
// VISIBILITY
// ======================================================

document.addEventListener(
    "visibilitychange",
    function(){

        if(
            document.visibilityState ===
            "visible"
        ){

            setTimeout(
                handleReturnFromAd,
                300
            );

        }

    }
);


// ======================================================
// PAGE SHOW
// ======================================================

window.addEventListener(
    "pageshow",
    function(){

        setTimeout(
            handleReturnFromAd,
            300
        );

    }
);


// ======================================================
// WINDOW MESSAGE
// ======================================================

window.addEventListener(
    "message",
    function(event){

        /*
         * Future compatibility.
         * Ad page থেকে message এলে unlock করা যাবে।
         */

        if(
            event.data ===
            "AD_COMPLETED"
        ){

            clearAdFlag();

            unlockVideo();

        }

    }
);


// ======================================================
// INIT
// ======================================================

loadVideo();


// ======================================================
// EXISTING AD FLAG
// ======================================================

/*
 * যদি browser/WebView Web App page-কে
 * restore করে, session flag থাকলে
 * return detect হবে।
 */

setTimeout(
    function(){

        if(
            wasAdStarted() &&
            document.visibilityState ===
            "visible"
        ){

            /*
             * শুধু page reload হয়েছে এমন অবস্থায়
             * সঙ্গে সঙ্গে unlock না করে focus/page
             * event-এর ওপর নির্ভর করি।
             */

        }

    },
    500
);


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


    try:

        if application_global is None:

            return web.Response(
                text="Telegram application not ready",
                status=503
            )


        telegram_file =
            await application_global.bot.get_file(
                content.file_id
            )


        file_url =
            telegram_file.file_path


        if not file_url:

            return web.Response(
                text="Telegram file URL unavailable",
                status=404
            )


        /*
         * Telegram file_path যদি relative হয়,
         * server-side bot token দিয়ে URL তৈরি হবে।
         *
         * এই URL browser-এর কাছে expose করা হবে না।
         */

        if not file_url.startswith(
            "http://"
        ) and not file_url.startswith(
            "https://"
        ):

            file_url = (
                "https://api.telegram.org/file/bot"
                + BOT_TOKEN
                + "/"
                + file_url
            )


        request_headers = {}


        range_header =
            request.headers.get(
                "Range"
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


                content_type =
                    upstream.headers.get(
                        "Content-Type",
                        "video/mp4"
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


                if upstream.headers.get(
                    "Last-Modified"
                ):

                    response_headers[
                        "Last-Modified"
                    ] = upstream.headers[
                        "Last-Modified"
                    ]


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


    except (
        asyncio.CancelledError
    ):

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
<meta name="viewport"
content="width=device-width,initial-scale=1">
<title>Advertisement</title>
</head>

<body style="
background:#111;
color:#fff;
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
<meta name="viewport"
content="width=device-width,initial-scale=1">
<title>Advertisement</title>
</head>

<body style="
background:#111;
color:#fff;
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


    /*
     * IMPORTANT:
     *
     * এই redirect server-side response।
     *
     * Telegram message-এ SmartLink দেওয়া হচ্ছে না।
     *
     * Web App থেকে /ad নতুন tab-এ open হচ্ছে।
     */

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
        "🌐 Web server running on "
        f"0.0.0.0:{PORT}"
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
    # TOKEN
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
    # ADMIN MEDIA
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
    # NOTIFICATION
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
    # ADMIN REQUESTS
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
    # REMINDERS
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
    # TELEGRAM START
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
    # KEEP ALIVE
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
