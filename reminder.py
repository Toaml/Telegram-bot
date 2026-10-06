# reminder.py
# ============================================================
# Telegram Bot - Automatic Reminder System
# ============================================================

import asyncio
import random
import datetime
from typing import Optional

import pytz
from telegram import Bot

from sqlalchemy import select

from config import DEFAULT_TIMEZONE
from database import AsyncSessionLocal, User

from prayer import get_prayer_times


# ============================================================
# TIMEZONE
# ============================================================

try:
    TZ = pytz.timezone(DEFAULT_TIMEZONE)
except Exception:
    TZ = pytz.timezone("Asia/Dhaka")


# ============================================================
# SCHEDULER STATE
# ============================================================

_scheduler_task = None
_scheduler_running = False

# Duplicate protection
_last_hour_sent = {}
_last_daily_sent = {}
_last_extra_sent = {}
_last_prayer_sent = {}


# ============================================================
# REMINDER MESSAGE DATABASE
# ============================================================

REMINDER_MESSAGES = {

    "wake": [
        "🌅 সুপ্রভাত! ঘুম থেকে ওঠার সময় হয়েছে। নতুন দিনটি সুন্দরভাবে শুরু করুন।",
        "☀️ সকাল হয়ে গেছে। ঘুম থেকে উঠে ফ্রেশ হয়ে দিনের কাজ শুরু করুন।",
        "🌄 নতুন একটি দিন শুরু হয়েছে। আজকের দিনটি ভালো কাজে ব্যবহার করুন।",
        "🌞 ঘুম থেকে ওঠার সময়। অলসতা বাদ দিয়ে আজকের কাজ শুরু করুন।",
        "🌅 সুপ্রভাত! আজকের দিনটি আপনার জন্য সুন্দর ও সফল হোক।",
        "☀️ উঠে পড়ুন! সকালটা নষ্ট না করে নিজের গুরুত্বপূর্ণ কাজগুলো শুরু করুন।",
        "🌄 সকাল এসেছে। একটু তাড়াতাড়ি উঠে দিনটাকে কাজে লাগান।",
        "🌞 নতুন সকাল, নতুন সুযোগ। ঘুম থেকে উঠে দিন শুরু করুন।"
    ],

    "breakfast": [
        "🍳 নাশতা করার সময় হয়েছে। শরীর সুস্থ রাখতে সকালের খাবার খেয়ে নিন।",
        "🥣 সকালবেলার খাবার খেতে ভুলবেন না। খালি পেটে বেশি সময় থাকবেন না।",
        "🍞 নাশতার সময়! ভালোভাবে খেয়ে দিনের কাজ শুরু করুন।",
        "🍳 শরীরের শক্তির জন্য সকালের নাশতা গুরুত্বপূর্ণ। সময়মতো খেয়ে নিন।",
        "🥛 নাশতা করে নিন। সুস্থ শরীরের জন্য নিয়মিত খাবার প্রয়োজন।",
        "🍽️ সকালের খাবারের সময় হয়েছে। নিজের যত্ন নিতে ভুলবেন না।",
        "🥚 আজকের নাশতা মিস করবেন না। স্বাস্থ্য ভালো রাখতে সময়মতো খাবার খান।",
        "🍌 কিছু পুষ্টিকর খাবার খেয়ে দিন শুরু করুন।"
    ],

    "study": [
        "📚 পড়াশোনার সময় হয়েছে। মনোযোগ দিয়ে কিছুক্ষণ পড়াশোনা করুন।",
        "📖 এখন পড়ার সময়। আজকের গুরুত্বপূর্ণ বিষয়গুলো শেষ করার চেষ্টা করুন।",
        "📝 বই-খাতা নিয়ে বসুন। নিয়মিত পড়াশোনা ভবিষ্যৎকে সুন্দর করে।",
        "🎓 পড়াশোনায় একটু সময় দিন। প্রতিদিনের ছোট অগ্রগতিই বড় সফলতা আনে।",
        "📚 মোবাইলটা কিছুক্ষণ দূরে রেখে পড়াশোনায় মন দিন।",
        "🧠 শেখার সময় হয়েছে। আজ নতুন কিছু শেখার চেষ্টা করুন।",
        "📖 আপনার লক্ষ্য মনে করুন এবং পড়াশোনা শুরু করুন।",
        "✍️ আজকের পড়া আজই শেষ করার চেষ্টা করুন।"
    ],

    "lunch": [
        "🍛 দুপুরের খাবারের সময় হয়েছে। সময়মতো দুপুরের খাবার খেয়ে নিন।",
        "🍚 দুপুরের খাবার খেতে ভুলবেন না। শরীরের প্রয়োজনীয় শক্তি বজায় রাখুন।",
        "🥗 লাঞ্চের সময়! ভালোভাবে খেয়ে কিছুক্ষণ বিশ্রাম নিন।",
        "🍲 দুপুর হয়ে গেছে। খাবার খাওয়ার সময় হয়েছে।",
        "🍛 কাজের মাঝে খাবার বাদ দেবেন না। সময়মতো দুপুরের খাবার খান।",
        "🥘 শরীর ভালো রাখতে দুপুরের খাবার সময়মতো খেয়ে নিন।",
        "🍚 দুপুরের খাবার প্রস্তুত? খেয়ে নিয়ে আবার কাজ শুরু করুন।",
        "🍽️ লাঞ্চ টাইম! নিজের স্বাস্থ্যের যত্ন নিন।"
    ],

    "bath": [
        "🚿 গোসল করার সময় হয়েছে। ফ্রেশ হয়ে নিন।",
        "🛁 শরীর সতেজ রাখতে গোসল করে নিন।",
        "🚿 একটু ফ্রেশ হওয়ার সময়। গোসল করে নিজেকে সতেজ করুন।",
        "🧼 পরিচ্ছন্নতা সুস্থতার একটি গুরুত্বপূর্ণ অংশ। গোসল করে নিন।",
        "🚿 অনেকক্ষণ কাজ করেছেন? এবার একটু ফ্রেশ হয়ে নিন।",
        "🛁 পরিষ্কার-পরিচ্ছন্ন থাকুন, সুস্থ থাকুন।",
        "🚿 গোসলের সময় হয়েছে। শরীর ও মন দুটোই সতেজ হবে।",
        "🧼 নিজের যত্ন নেওয়ার সময়। একটু ফ্রেশ হয়ে নিন।"
    ],

    "sports": [
        "⚽ খেলাধুলা বা শরীরচর্চার সময় হয়েছে। একটু নড়াচড়া করুন।",
        "🏃 শরীর সুস্থ রাখতে কিছুক্ষণ হাঁটুন বা ব্যায়াম করুন।",
        "⚽ বাইরে গিয়ে খেলাধুলা করতে পারেন। শরীরচর্চা স্বাস্থ্যের জন্য ভালো।",
        "🏃 দীর্ঘসময় বসে থাকবেন না। একটু হাঁটাহাঁটি করুন।",
        "💪 শরীরকে সক্রিয় রাখুন। কিছুক্ষণ ব্যায়াম বা খেলাধুলা করুন।",
        "⚽ মন ভালো করার জন্য একটু খেলাধুলা করুন।",
        "🏃 আজকের শরীরচর্চা হয়েছে তো? এখনই কিছুক্ষণ সময় দিন।",
        "💪 সুস্থ শরীরের জন্য নিয়মিত নড়াচড়া জরুরি।"
    ],

    "water": [
        "💧 পানি খাওয়ার সময় হয়েছে। এক গ্লাস পানি পান করুন।",
        "🥤 শরীরকে পানিশূন্য হতে দেবেন না। পানি পান করুন।",
        "💧 আপনি শেষ কবে পানি খেয়েছেন? এখন এক গ্লাস পানি পান করুন।",
        "🚰 পর্যাপ্ত পানি পান করা স্বাস্থ্যের জন্য গুরুত্বপূর্ণ।",
        "💧 একটু পানি পান করুন এবং শরীরকে সতেজ রাখুন।",
        "🥤 পানি খেতে ভুলবেন না।",
        "💧 শরীরের প্রয়োজন অনুযায়ী পানি পান করুন।",
        "🚰 এখনই এক গ্লাস পরিষ্কার পানি পান করতে পারেন।"
    ],

    "work": [
        "💼 কাজের সময় হয়েছে। আজকের গুরুত্বপূর্ণ কাজগুলো শুরু করুন।",
        "🧑‍💻 কাজের দিকে মনোযোগ দেওয়ার সময়।",
        "📋 আজকের কাজের তালিকা দেখে একটি একটি করে শেষ করুন।",
        "💼 সময় নষ্ট না করে প্রয়োজনীয় কাজ শুরু করুন।",
        "🧠 মনোযোগ দিয়ে কাজ করুন। ছোট অগ্রগতিও গুরুত্বপূর্ণ।",
        "📌 গুরুত্বপূর্ণ কাজগুলো আগে শেষ করার চেষ্টা করুন।",
        "💻 কাজের সময় হয়েছে। মনোযোগ ধরে রাখুন।",
        "🚀 আজকের লক্ষ্য পূরণের জন্য এখনই কাজে মন দিন।"
    ],

    "evening": [
        "🌇 সন্ধ্যা হয়েছে। দিনের কাজগুলো একবার গুছিয়ে নিন।",
        "🌆 সন্ধ্যার সময়। একটু বিশ্রাম নিয়ে পরিবারের সঙ্গে সময় কাটাতে পারেন।",
        "🌇 দিন প্রায় শেষ। আজ কী কী করেছেন একটু ভাবুন।",
        "🌆 সন্ধ্যা নেমেছে। মনকে শান্ত রাখুন এবং ভালো সময় কাটান।",
        "🌇 সন্ধ্যার সুন্দর সময়টি উপভোগ করুন।",
        "🕌 সন্ধ্যার সময় নামাজের কথাও মনে রাখুন।",
        "🌆 দিনের ব্যস্ততার পর একটু বিশ্রাম নিন।",
        "🌇 সন্ধ্যা হয়েছে। আগামী কাজের জন্য নিজেকে প্রস্তুত করুন।"
    ],

    "dinner": [
        "🍽️ রাতের খাবারের সময় হয়েছে। সময়মতো খাবার খেয়ে নিন।",
        "🍛 ডিনারের সময়! স্বাস্থ্য ভালো রাখতে খাবার বাদ দেবেন না।",
        "🥗 রাতের খাবার খেয়ে নিন এবং অতিরিক্ত রাত জাগা এড়িয়ে চলুন।",
        "🍚 রাতের খাবারের সময় হয়েছে। নিজের যত্ন নিন।",
        "🍽️ আজকের দিনের শেষ খাবারটি সময়মতো খেয়ে নিন।",
        "🥘 খাবার খাওয়ার সময় হয়েছে। সুস্থ থাকার জন্য নিয়ম মেনে চলুন।",
        "🍛 ডিনার করে কিছুক্ষণ বিশ্রাম নিন।",
        "🍽️ রাতের খাবার খেতে ভুলবেন না।"
    ],

    "sleep": [
        "😴 ঘুমানোর সময় হয়েছে। পর্যাপ্ত ঘুম শরীর ও মনের জন্য গুরুত্বপূর্ণ।",
        "🌙 আজ অনেক হয়েছে। এখন মোবাইল রেখে ঘুমানোর প্রস্তুতি নিন।",
        "😴 শরীরকে বিশ্রাম দিন। সময়মতো ঘুমানোর চেষ্টা করুন।",
        "🌙 শুভরাত্রি! আগামী দিনের জন্য পর্যাপ্ত ঘুম নিন।",
        "🛌 ঘুমের সময় হয়েছে। ভালো ঘুম আপনার কর্মক্ষমতা বাড়াতে সাহায্য করে।",
        "🌙 রাত বেশি করবেন না। এখন বিশ্রামের সময়।",
        "😴 দিনের কাজ শেষ করুন এবং ঘুমের প্রস্তুতি নিন।",
        "🛏️ শরীর ও মনের বিশ্রামের জন্য এখন ঘুমিয়ে পড়ুন।"
    ],

    "motivation": [
        "💪 হাল ছাড়বেন না। ধীরে ধীরে এগোলেও আপনি এগিয়ে যাচ্ছেন।",
        "🌟 নিজের উপর বিশ্বাস রাখুন। চেষ্টা কখনো বৃথা যায় না।",
        "🚀 আজকের ছোট একটি পদক্ষেপ ভবিষ্যতের বড় পরিবর্তন আনতে পারে।",
        "🔥 লক্ষ্য ঠিক রাখুন এবং নিয়মিত চেষ্টা চালিয়ে যান।",
        "💎 কঠিন সময় স্থায়ী নয়। চেষ্টা চালিয়ে যান।",
        "🌱 প্রতিদিন নিজেকে গতকালের চেয়ে একটু ভালো করার চেষ্টা করুন।",
        "🏆 সফলতার জন্য ধৈর্য, পরিশ্রম এবং নিয়মিত চেষ্টা প্রয়োজন।",
        "✨ আপনার সময় আসবে। শুধু চেষ্টা থামাবেন না।"
    ],

    "family": [
        "❤️ পরিবারের মানুষগুলোর খোঁজ নিন। তাদের সঙ্গে কিছু সময় কাটান।",
        "👨‍👩‍👧‍👦 পরিবারের সঙ্গে ভালোভাবে কথা বলুন। পরিবার আমাদের বড় শক্তি।",
        "❤️ কাছের মানুষদের সময় দিন। ছোট একটি কথাও কারও মন ভালো করতে পারে।",
        "🏠 পরিবারের কারও কোনো সাহায্য দরকার কি না দেখে নিন।",
        "💖 প্রিয় মানুষদের প্রতি ভালোবাসা প্রকাশ করতে ভুলবেন না।",
        "👪 পরিবারের সঙ্গে কিছু সুন্দর সময় কাটানোর চেষ্টা করুন।",
        "❤️ বাবা-মায়ের খোঁজ নিন এবং তাদের সম্মান করুন।",
        "🏡 পরিবারের শান্তি ও ভালোবাসাকে মূল্য দিন।"
    ],

    "habit": [
        "✅ আজ একটি ভালো অভ্যাস ধরে রাখুন।",
        "🌱 ছোট ভালো অভ্যাসই ভবিষ্যতে বড় পরিবর্তন আনে।",
        "📌 আজকের কাজ আজই শেষ করার চেষ্টা করুন।",
        "⏰ সময়ের মূল্য দিন। সময় একবার চলে গেলে ফিরে আসে না।",
        "🧹 নিজের আশপাশটা একটু পরিষ্কার করে নিন।",
        "📖 প্রতিদিন নতুন কিছু শেখার অভ্যাস করুন।",
        "💧 পানি পান, নিয়মিত খাবার ও পর্যাপ্ত ঘুমের দিকে খেয়াল রাখুন।",
        "📵 কিছু সময় ফোন থেকে দূরে থেকে নিজের কাজে মন দিন।"
    ],

    "islamic": [
        "🕌 আল্লাহকে স্মরণ করুন এবং নিজের নামাজের প্রতি যত্নবান হোন।",
        "🤲 আল্লাহর কাছে দোয়া করুন। নিজের ও পরিবারের জন্য কল্যাণ কামনা করুন।",
        "📿 কিছু সময় জিকির ও ইবাদতে কাটাতে পারেন।",
        "🕌 নামাজ সময়মতো আদায় করার চেষ্টা করুন।",
        "🤲 আল্লাহ আমাদের সবাইকে সঠিক পথে চলার তাওফিক দিন। আমিন।",
        "❤️ মানুষের সঙ্গে ভালো ব্যবহার করাও উত্তম আমল।",
        "🕋 নিজের ভুলের জন্য আল্লাহর কাছে ক্ষমা চান এবং ভালো কাজের চেষ্টা করুন।",
        "🤲 আজ কাউকে একটি ভালো কথা বলুন এবং কারও উপকার করুন।"
    ]
}


# ============================================================
# EXTRA MESSAGE ENDINGS
# ============================================================

MESSAGE_ENDINGS = [
    "",
    "\n\n🌸 নিজের যত্ন নিন।",
    "\n\n💚 সুস্থ থাকুন, ভালো থাকুন।",
    "\n\n✨ আজকের দিনটি সুন্দর হোক।",
    "\n\n❤️ আপনার জন্য শুভকামনা।",
    "\n\n🤲 আল্লাহ আমাদের সবাইকে ভালো রাখুন।",
    "\n\n🌿 শান্ত থাকুন এবং ভালো কাজ করুন।",
    "\n\n💫 ছোট ছোট ভালো কাজ চালিয়ে যান।",
    "\n\n😊 হাসিমুখে দিনটি কাটান।",
    "\n\n⭐ নিজের লক্ষ্য ভুলবেন না।"
]


# ============================================================
# GET RANDOM MESSAGE
# ============================================================

def get_reminder_message(reminder_type: str) -> str:

    messages = REMINDER_MESSAGES.get(
        reminder_type,
        REMINDER_MESSAGES["motivation"]
    )

    message = random.choice(messages)

    # Random ending যোগ করে অনেক variation তৈরি
    ending = random.choice(MESSAGE_ENDINGS)

    return message + ending


# ============================================================
# HOURLY TIME MESSAGE
# ============================================================

def get_time_message() -> str:

    now = datetime.datetime.now(TZ)

    hour = now.hour
    minute = now.minute

    if hour == 0:
        display_hour = 12
        period = "রাত"
    elif hour < 12:
        display_hour = hour
        period = "সকাল"
    elif hour == 12:
        display_hour = 12
        period = "দুপুর"
    elif hour < 18:
        display_hour = hour - 12
        period = "বিকেল"
    else:
        display_hour = hour - 12
        period = "রাত"

    return (
        f"🕐 এখন সময় {display_hour:02d}:{minute:02d} বাজে।\n\n"
        f"⏰ {period} — সময়ের মূল্য দিন এবং আপনার প্রয়োজনীয় "
        f"কাজে মনোযোগ দিন।"
    )


# ============================================================
# PRAYER INFORMATION
# ============================================================

PRAYER_INFO = {

    "Fajr": {
        "name": "ফজর",
        "emoji": "🌅",
        "benefit": "দিনের শুরু আল্লাহর ইবাদত দিয়ে করার সুন্দর সুযোগ।"
    },

    "Dhuhr": {
        "name": "যোহর",
        "emoji": "☀️",
        "benefit": "ব্যস্ততার মাঝেও আল্লাহকে স্মরণ করার সময়।"
    },

    "Asr": {
        "name": "আসর",
        "emoji": "🌤️",
        "benefit": "দিনের ব্যস্ততার মাঝে নামাজের মাধ্যমে নিজেকে স্মরণ করিয়ে দিন।"
    },

    "Maghrib": {
        "name": "মাগরিব",
        "emoji": "🌇",
        "benefit": "সন্ধ্যার শুরুতে আল্লাহর ইবাদতের সুন্দর সময়।"
    },

    "Isha": {
        "name": "এশা",
        "emoji": "🌙",
        "benefit": "দিনের শেষ নামাজ আদায় করে শান্ত মনে বিশ্রামের প্রস্তুতি নিন।"
    }
}


# ============================================================
# DATABASE USER FUNCTIONS
# ============================================================

async def get_all_users():

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
        )

        return result.scalars().all()


async def get_user(user_id: int):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.user_id == user_id
            )
        )

        return result.scalars().first()


# ============================================================
# SAFE SEND
# ============================================================

async def safe_send(
    bot: Bot,
    user_id: int,
    message: str
):

    try:

        await bot.send_message(
            chat_id=user_id,
            text=message,
            disable_web_page_preview=True
        )

        return True

    except Exception as e:

        print(
            f"[Reminder] Failed to send to {user_id}: {e}"
        )

        return False


# ============================================================
# PRAYER CACHE
# ============================================================

_prayer_cache = {}


async def get_cached_prayer_times(
    city: str = "Dhaka"
):

    today = datetime.datetime.now(TZ).strftime(
        "%Y-%m-%d"
    )

    cache_key = f"{city}_{today}"

    if cache_key in _prayer_cache:

        return _prayer_cache[cache_key]

    try:

        prayer_times = await get_prayer_times(
            city=city,
            country="Bangladesh"
        )

        if prayer_times:

            _prayer_cache[cache_key] = prayer_times

            return prayer_times

    except Exception as e:

        print(
            f"[Prayer] Failed for {city}: {e}"
        )

    return None


# ============================================================
# SEND PRAYER REMINDERS
# ============================================================

async def send_prayer_reminders(
    bot: Bot
):

    now = datetime.datetime.now(TZ)

    current_time = now.strftime(
        "%H:%M"
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    users = await get_all_users()

    for user in users:

        try:

            if not user.prayer_notify:
                continue

            city = user.city or "Dhaka"

            prayer_times = await get_cached_prayer_times(
                city
            )

            if not prayer_times:
                continue

            for prayer_key in [
                "Fajr",
                "Dhuhr",
                "Asr",
                "Maghrib",
                "Isha"
            ]:

                api_time = prayer_times.get(
                    prayer_key
                )

                if not api_time:
                    continue

                prayer_time = str(
                    api_time
                )[:5]

                if prayer_time != current_time:
                    continue

                dedupe_key = (
                    user.user_id,
                    today,
                    prayer_key
                )

                if _last_prayer_sent.get(
                    dedupe_key
                ):
                    continue

                info = PRAYER_INFO[
                    prayer_key
                ]

                message = (
                    f"{info['emoji']} *{info['name']} নামাজের সময় হয়েছে!*\n\n"
                    f"🕌 সময়: {prayer_time}\n\n"
                    f"🤲 সবাই নামাজ আদায় করুন।\n\n"
                    f"🌿 গুরুত্ব: {info['benefit']}\n\n"
                    f"আল্লাহ আমাদের সবাইকে নামাজ কায়েম করার তাওফিক দিন। "
                    f"আমিন।"
                )

                success = await safe_send(
                    bot,
                    user.user_id,
                    message
                )

                if success:

                    _last_prayer_sent[
                        dedupe_key
                    ] = True

        except Exception as e:

            print(
                f"[Prayer] User error {user.user_id}: {e}"
            )


# ============================================================
# DAILY SCHEDULE
# ============================================================

DAILY_SCHEDULE = [

    ("06:30", "wake", "wake_notify"),

    ("08:00", "breakfast", "food_notify"),

    ("10:00", "study", "study_notify"),

    ("12:30", "lunch", "food_notify"),

    ("14:30", "bath", "custom_notify"),

    ("16:30", "sports", "play_notify"),

    ("18:30", "evening", "custom_notify"),

    ("20:30", "dinner", "food_notify"),

    ("22:30", "sleep", "sleep_notify"),
]


# ============================================================
# EXTRA SCHEDULE
# ============================================================

EXTRA_SCHEDULE = [

    ("07:30", "water", "custom_notify"),

    ("09:30", "habit", "custom_notify"),

    ("11:30", "water", "custom_notify"),

    ("15:30", "water", "custom_notify"),

    ("17:30", "motivation", "custom_notify"),

    ("19:30", "family", "custom_notify"),

    ("21:30", "islamic", "custom_notify"),
]


# ============================================================
# SEND DAILY REMINDERS
# ============================================================

async def send_daily_reminders(
    bot: Bot
):

    now = datetime.datetime.now(TZ)

    current_time = now.strftime(
        "%H:%M"
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    users = await get_all_users()

    for user in users:

        try:

            for schedule_time, reminder_type, setting in DAILY_SCHEDULE:

                if schedule_time != current_time:
                    continue

                if not getattr(
                    user,
                    setting,
                    True
                ):
                    continue

                dedupe_key = (
                    user.user_id,
                    today,
                    schedule_time,
                    reminder_type
                )

                if _last_daily_sent.get(
                    dedupe_key
                ):
                    continue

                message = get_reminder_message(
                    reminder_type
                )

                success = await safe_send(
                    bot,
                    user.user_id,
                    message
                )

                if success:

                    _last_daily_sent[
                        dedupe_key
                    ] = True

        except Exception as e:

            print(
                f"[Daily] User error {user.user_id}: {e}"
            )


# ============================================================
# SEND EXTRA REMINDERS
# ============================================================

async def send_extra_reminders(
    bot: Bot
):

    now = datetime.datetime.now(TZ)

    current_time = now.strftime(
        "%H:%M"
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    users = await get_all_users()

    for user in users:

        try:

            for schedule_time, reminder_type, setting in EXTRA_SCHEDULE:

                if schedule_time != current_time:
                    continue

                if not getattr(
                    user,
                    setting,
                    True
                ):
                    continue

                dedupe_key = (
                    user.user_id,
                    today,
                    schedule_time,
                    reminder_type
                )

                if _last_extra_sent.get(
                    dedupe_key
                ):
                    continue

                message = get_reminder_message(
                    reminder_type
                )

                success = await safe_send(
                    bot,
                    user.user_id,
                    message
                )

                if success:

                    _last_extra_sent[
                        dedupe_key
                    ] = True

        except Exception as e:

            print(
                f"[Extra] User error {user.user_id}: {e}"
            )


# ============================================================
# SEND HOURLY TIME
# ============================================================

async def send_hourly_time(
    bot: Bot
):

    now = datetime.datetime.now(TZ)

    # প্রতি ঘণ্টার শুরুতে
    if now.minute != 0:
        return

    hour_key = now.strftime(
        "%Y-%m-%d-%H"
    )

    # একই ঘণ্টায় দ্বিতীয়বার পাঠাবে না
    if _last_hour_sent.get(
        "global"
    ) == hour_key:
        return

    users = await get_all_users()

    message = get_time_message()

    sent_any = False

    for user in users:

        try:

            if not user.hourly_notify:
                continue

            success = await safe_send(
                bot,
                user.user_id,
                message
            )

            if success:
                sent_any = True

        except Exception as e:

            print(
                f"[Hourly] User error {user.user_id}: {e}"
            )

    if sent_any:

        _last_hour_sent[
            "global"
        ] = hour_key


# ============================================================
# CLEAN OLD DEDUPE DATA
# ============================================================

def cleanup_dedupe_cache():

    if len(_last_daily_sent) > 5000:

        _last_daily_sent.clear()

    if len(_last_extra_sent) > 5000:

        _last_extra_sent.clear()

    if len(_last_prayer_sent) > 5000:

        _last_prayer_sent.clear()


# ============================================================
# MAIN REMINDER LOOP
# ============================================================

async def reminder_loop(
    application
):

    global _scheduler_running

    # --------------------------------------------------------
    # IMPORTANT:
    # bot.py থেকে scheduler শুরু হওয়ার সময় Telegram Bot
    # এখনও initialize নাও হয়ে থাকতে পারে।
    #
    # এই initialize() call-টাই Render-এর
    # "ExtBot is not properly initialized"
    # সমস্যাটি ঠিক করে।
    # --------------------------------------------------------

    try:

        await application.bot.initialize()

        print(
            "[Reminder] Telegram bot initialized successfully."
        )

    except Exception as e:

        print(
            f"[Reminder] Bot initialization error: {e}"
        )

        _scheduler_running = False

        return

    print(
        "[Reminder] Automatic reminder scheduler started."
    )

    while _scheduler_running:

        try:

            bot = application.bot

            # প্রতি ঘণ্টার notification
            await send_hourly_time(
                bot
            )

            # নামাজের notification
            await send_prayer_reminders(
                bot
            )

            # দৈনিক notification
            await send_daily_reminders(
                bot
            )

            # Extra notification
            await send_extra_reminders(
                bot
            )

            cleanup_dedupe_cache()

        except asyncio.CancelledError:

            print(
                "[Reminder] Scheduler cancelled."
            )

            break

        except Exception as e:

            print(
                f"[Reminder] Loop error: {e}"
            )

        # প্রতি 20 সেকেন্ডে check করবে
        await asyncio.sleep(20)


# ============================================================
# START SCHEDULER
# ============================================================

def start_scheduler(
    application
):

    global _scheduler_task
    global _scheduler_running

    if _scheduler_task is not None:

        if not _scheduler_task.done():

            print(
                "[Reminder] Scheduler already running."
            )

            return

    _scheduler_running = True

    # IMPORTANT:
    # application.bot সরাসরি access করে task শুরু করা হচ্ছে না।
    # পুরো application পাঠানো হচ্ছে।
    _scheduler_task = asyncio.create_task(
        reminder_loop(
            application
        )
    )

    print(
        "[Reminder] Scheduler task created."
    )


# ============================================================
# STOP SCHEDULER
# ============================================================

async def stop_scheduler():

    global _scheduler_task
    global _scheduler_running

    _scheduler_running = False

    if _scheduler_task is not None:

        if not _scheduler_task.done():

            _scheduler_task.cancel()

            try:

                await _scheduler_task

            except asyncio.CancelledError:

                pass

            except Exception as e:

                print(
                    f"[Reminder] Stop error: {e}"
                )

    _scheduler_task = None

    print(
        "[Reminder] Scheduler stopped."
    )


# ============================================================
# RELOAD REMINDERS
# ============================================================

def reload_reminders(
    application
):

    global _scheduler_task
    global _scheduler_running

    # পুরোনো task বন্ধ
    if _scheduler_task is not None:

        if not _scheduler_task.done():

            _scheduler_running = False

            _scheduler_task.cancel()

    _scheduler_task = None

    # নতুন task চালু
    _scheduler_running = True

    _scheduler_task = asyncio.create_task(
        reminder_loop(
            application
        )
    )

    print(
        "[Reminder] Scheduler reloaded."
    )


# ============================================================
# TEST REMINDER
# ============================================================

async def test_reminder(
    bot: Bot,
    user_id: int
):

    message = (
        "🔔 *Reminder Test Successful!*\n\n"
        "✅ আপনার Automatic Reminder System কাজ করছে।\n\n"
        "🕌 Prayer Reminder\n"
        "🕐 Hourly Reminder\n"
        "🌅 Daily Reminder\n"
        "💧 Water Reminder\n"
        "📚 Study Reminder\n"
        "💼 Work Reminder\n"
        "⚽ Play Reminder\n"
        "😴 Sleep Reminder\n\n"
        "সবগুলো Scheduler-এর মাধ্যমে নির্ধারিত সময়ে "
        "স্বয়ংক্রিয়ভাবে পাঠানো হবে।"
    )

    return await safe_send(
        bot,
        user_id,
        message
    )


# ============================================================
# END
# ============================================================# reminder.py
# Telegram Automatic Reminder System
# User online/offline — bot sends automatically
# Persistent users are loaded from database

import asyncio
import random
import datetime
from typing import Optional

import pytz
from telegram import Bot

from config import DEFAULT_TIMEZONE
from database import AsyncSessionLocal, User
from sqlalchemy import select

from prayer import get_prayer_times


# ============================================================
# TIMEZONE
# ============================================================

try:
    TZ = pytz.timezone(DEFAULT_TIMEZONE)
except Exception:
    TZ = pytz.timezone("Asia/Dhaka")


# ============================================================
# SCHEDULER STATE
# ============================================================

_scheduler_task: Optional[asyncio.Task] = None
_scheduler_running = False


# ============================================================
# ANTI-DUPLICATE MEMORY
# ============================================================

_last_hour_sent = {}
_last_prayer_sent = {}
_last_daily_sent = {}
_last_extra_sent = {}

_message_history = {}


# ============================================================
# 500+ MESSAGE VARIATIONS
# ============================================================

BASE_MESSAGES = {

    "wake": [
        "🌅 সুপ্রভাত! ঘুম থেকে ওঠার সময় হয়েছে।",
        "☀️ সকাল হয়ে গেছে। এবার ঘুম থেকে উঠে নতুন দিন শুরু করুন।",
        "🌞 ঘুম থেকে ওঠার সময় হয়েছে। আজকের দিনটি সুন্দরভাবে শুরু করুন।",
        "🌅 উঠে পড়ুন! নতুন একটি দিন আপনার জন্য অপেক্ষা করছে।",
        "⏰ সকাল হয়েছে। ঘুম থেকে উঠে নিজেকে সতেজ করুন।",
        "🌄 শুভ সকাল! অলসতা ছেড়ে দিনের শুরুটা সুন্দর করুন।",
        "☀️ ঘুম থেকে উঠে আল্লাহর শুকরিয়া আদায় করুন এবং দিন শুরু করুন।",
        "🌞 নতুন সকাল, নতুন সুযোগ। উঠে পড়ুন।",
        "🌅 সকাল শুরু হয়ে গেছে। আজকের কাজগুলো পরিকল্পনা করুন।",
        "⏰ উঠে পড়ার সময়। সুন্দর একটি দিন আপনার অপেক্ষায়।",
    ],

    "breakfast": [
        "🍳 নাশতা করার সময় হয়েছে। দিনের শুরুতে পুষ্টিকর খাবার খান।",
        "🥪 সকালের খাবার খেতে ভুলবেন না।",
        "🍞 শরীরকে শক্তি দিতে সকালের নাশতা করুন।",
        "🥛 নাশতা করে দিনটি শক্তি নিয়ে শুরু করুন।",
        "🍳 সকালের খাবার বাদ দেবেন না। নিজের যত্ন নিন।",
        "🥗 স্বাস্থ্যকর নাশতা আপনার দিনকে আরও ভালো করতে পারে।",
        "☕ সকাল হয়েছে—সময়মতো নাশতা করে নিন।",
        "🍌 ফল বা পুষ্টিকর খাবার দিয়ে সকাল শুরু করতে পারেন।",
        "🍽️ নাশতার সময় হয়েছে। শরীরকে প্রয়োজনীয় শক্তি দিন।",
        "🌞 সুন্দর দিনের জন্য সকালের খাবার খেয়ে নিন।",
    ],

    "study": [
        "📚 পড়াশোনার সময় হয়েছে। মনোযোগ দিয়ে কিছুক্ষণ পড়ুন।",
        "📝 আজকের পড়াশোনাটা শুরু করুন। ছোট অগ্রগতিও গুরুত্বপূর্ণ।",
        "📖 বই খুলে বসার সময় হয়েছে।",
        "🎓 নিজের ভবিষ্যতের জন্য কিছু সময় পড়াশোনায় দিন।",
        "📚 মনোযোগ দিয়ে পড়ুন—আজকের পরিশ্রম ভবিষ্যতে কাজে আসবে।",
        "🧠 নতুন কিছু শেখার সময় হয়েছে।",
        "✏️ পড়াশোনার জন্য কয়েক মিনিট হলেও সময় বের করুন।",
        "📖 নিয়মিত পড়াশোনা আপনাকে লক্ষ্যের কাছে নিয়ে যাবে।",
        "🎯 আপনার লক্ষ্য মনে করুন এবং পড়াশোনা শুরু করুন।",
        "📚 আজকের পড়া আজই শেষ করার চেষ্টা করুন।",
    ],

    "lunch": [
        "🍛 দুপুরের খাবারের সময় হয়েছে। সময়মতো খাবার খান।",
        "🍚 দুপুরের খাবার খেয়ে নিন এবং শরীরকে শক্তি দিন।",
        "🥗 দুপুরে পুষ্টিকর খাবার খাওয়ার সময় হয়েছে।",
        "🍽️ লাঞ্চের সময়। কাজের মাঝে খাবার খেতে ভুলবেন না।",
        "🍛 দুপুরের খাবার বাদ দেবেন না।",
        "🥘 সময়মতো খাবার খাওয়া শরীরের জন্য ভালো।",
        "🍚 দুপুর হয়েছে—খাবার খেয়ে একটু বিশ্রাম নিন।",
        "🍽️ নিজের যত্ন নিন। দুপুরের খাবার খেয়ে নিন।",
        "🥗 স্বাস্থ্যকর খাবার বেছে নিন এবং পর্যাপ্ত পানি পান করুন।",
        "🍛 খাবারের সময় হয়েছে। কাজ কিছুক্ষণের জন্য থামিয়ে খাবার খান।",
    ],

    "bath": [
        "🚿 গোসল করার সময় হয়েছে। নিজেকে সতেজ করে নিন।",
        "🛁 একটু সময় নিয়ে গোসল করে ফ্রেশ হয়ে নিন।",
        "🚿 শরীর ও মন সতেজ করতে গোসল করে নিন।",
        "✨ ফ্রেশ হওয়ার সময়। গোসল করে নতুনভাবে কাজ শুরু করুন।",
        "🧼 নিজের পরিচ্ছন্নতার দিকে খেয়াল রাখুন।",
        "🚿 গোসল করে শরীরকে সতেজ রাখুন।",
        "🛁 ব্যস্ততার মাঝেও নিজের যত্ন নিন।",
        "🌿 ফ্রেশ হয়ে বাকি কাজগুলো শুরু করুন।",
    ],

    "sports": [
        "⚽ খেলাধুলা বা ব্যায়ামের সময় হয়েছে।",
        "🏃 কিছুক্ষণ হাঁটাহাঁটি বা ব্যায়াম করুন।",
        "💪 শরীরকে সক্রিয় রাখুন। একটু ব্যায়াম করুন।",
        "⚽ খেলাধুলার জন্য কিছু সময় বের করুন।",
        "🏃 দীর্ঘ সময় বসে থাকলে একটু হাঁটুন।",
        "💪 শরীর সুস্থ রাখতে নিয়মিত নড়াচড়া করুন।",
        "🏋️ কয়েক মিনিট ব্যায়াম করলেও উপকার পাওয়া যায়।",
        "⚽ মন ভালো রাখতে একটু খেলাধুলা করুন।",
    ],

    "water": [
        "💧 পানি পান করার সময় হয়েছে। এক গ্লাস পানি পান করুন।",
        "🥤 শরীরকে পানিশূন্যতা থেকে রক্ষা করতে পানি পান করুন।",
        "💧 অনেকক্ষণ পানি পান করেছেন কি? এখন এক গ্লাস পানি পান করুন।",
        "🚰 নিজের শরীরের যত্ন নিন—পানি পান করুন।",
        "💦 পানি পান করতে ভুলবেন না।",
        "🥛 এখন একটু পানি পান করে নিন।",
        "💧 পর্যাপ্ত পানি পান করা স্বাস্থ্যকর অভ্যাসের অংশ।",
        "🚰 কাজের ফাঁকে পানি খেয়ে নিন।",
    ],

    "work": [
        "💼 কাজের সময় হয়েছে। মনোযোগ দিয়ে কাজ শুরু করুন।",
        "📋 আজকের গুরুত্বপূর্ণ কাজগুলো শেষ করার চেষ্টা করুন।",
        "💻 কাজের দিকে মনোযোগ দেওয়ার সময় হয়েছে।",
        "🎯 একটি একটি করে কাজ শেষ করুন।",
        "💼 সময়কে কাজে লাগান।",
        "📌 আজকের দায়িত্বগুলো মনে করুন এবং কাজ শুরু করুন।",
        "🚀 ছোট ছোট কাজ শেষ করেই বড় লক্ষ্য অর্জন হয়।",
        "💻 কাজের মাঝে অযথা সময় নষ্ট করবেন না।",
        "🎯 আপনার লক্ষ্য অনুযায়ী কাজ এগিয়ে নিন।",
        "💼 আজকের কাজ আজই শেষ করার চেষ্টা করুন।",
    ],

    "evening": [
        "🌇 সন্ধ্যা হয়ে গেছে। দিনের কাজগুলো একটু গুছিয়ে নিন।",
        "🌆 সুন্দর সন্ধ্যা। পরিবারকে একটু সময় দিন।",
        "🌇 সন্ধ্যার সময়টি শান্তভাবে কাটান।",
        "🌆 দিনের ব্যস্ততার পর কিছুক্ষণ বিশ্রাম নিন।",
        "☕ সন্ধ্যা হয়েছে। নিজের ও পরিবারের খোঁজ নিন।",
        "🌇 আজকের দিনটি কেমন গেল একটু ভাবুন।",
        "🌆 সন্ধ্যার সময়টি ভালো কাজে ব্যবহার করুন।",
        "✨ সন্ধ্যা হয়েছে—মনকে একটু শান্ত করুন।",
    ],

    "dinner": [
        "🍽️ রাতের খাবারের সময় হয়েছে। সময়মতো খাবার খান।",
        "🍛 রাতের খাবার খেয়ে নিন।",
        "🥗 হালকা ও পরিমিত খাবার খাওয়ার চেষ্টা করুন।",
        "🍚 রাত হয়েছে—খাবার খেতে ভুলবেন না।",
        "🍽️ পরিবারের সঙ্গে রাতের খাবার খেতে পারেন।",
        "🥘 সময়মতো রাতের খাবার শেষ করুন।",
        "🍛 নিজের শরীরের যত্ন নিন এবং খাবার খান।",
        "🌙 রাতের খাবারের সময় হয়েছে।",
    ],

    "sleep": [
        "😴 ঘুমানোর সময় হয়েছে। আজকের কাজ শেষ করে বিশ্রাম নিন।",
        "🌙 এবার ঘুমের প্রস্তুতি নিন। শরীরের বিশ্রাম দরকার।",
        "😴 পর্যাপ্ত ঘুম আপনার শরীর ও মনের জন্য গুরুত্বপূর্ণ।",
        "🌙 মোবাইল কিছুক্ষণ দূরে রেখে ঘুমের প্রস্তুতি নিন।",
        "🛌 আগামীকালের জন্য শরীরকে বিশ্রাম দিন।",
        "😴 রাত হয়েছে। আজকের দিনটি এখানেই শেষ করুন।",
        "🌙 শান্তভাবে ঘুমানোর প্রস্তুতি নিন।",
        "🛏️ সময়মতো ঘুমানোর চেষ্টা করুন।",
        "😴 বিশ্রাম নিন, আগামীকাল নতুন দিন।",
        "🌙 শুভরাত্রি। আল্লাহ আপনাকে শান্তিতে রাখুন।",
    ],

    "motivation": [
        "💪 হাল ছাড়বেন না। ধীরে ধীরে এগিয়ে যান।",
        "🌟 আজকের ছোট চেষ্টা আগামীকালের বড় সাফল্য হতে পারে।",
        "🎯 নিজের লক্ষ্য মনে রাখুন।",
        "🔥 আপনি পারবেন—শুধু চেষ্টা চালিয়ে যান।",
        "💪 ব্যর্থতা মানেই শেষ নয়। আবার চেষ্টা করুন।",
        "🌱 প্রতিদিন একটু একটু করে উন্নতি করুন।",
        "🚀 সময়কে কাজে লাগান।",
        "⭐ নিজের ওপর বিশ্বাস রাখুন।",
        "🎯 অজুহাত নয়, কাজ শুরু করুন।",
        "💙 কঠিন সময়ও একদিন পার হয়ে যাবে।",
    ],

    "family": [
        "❤️ পরিবারের মানুষগুলোর খোঁজ নিন।",
        "👨‍👩‍👧 পরিবারের সঙ্গে কিছু সময় কাটান।",
        "❤️ প্রিয়জনকে একটি ভালো কথা বলুন।",
        "🏠 পরিবারের মানুষদের মূল্য দিন।",
        "💖 কাছের মানুষদের সঙ্গে ভালো ব্যবহার করুন।",
        "👨‍👩‍👧 পরিবারের কারও প্রয়োজন আছে কি না খোঁজ নিন।",
        "❤️ একটি ছোট ভালোবাসার কথা কারও দিনটা সুন্দর করতে পারে।",
        "🏡 পরিবারকে সময় দেওয়া গুরুত্বপূর্ণ।",
    ],

    "habit": [
        "✨ আজ একটি ভালো অভ্যাস তৈরি করুন।",
        "🧹 নিজের চারপাশ পরিষ্কার রাখুন।",
        "📵 কিছুক্ষণ অপ্রয়োজনীয় মোবাইল ব্যবহার বন্ধ রাখুন।",
        "🧠 নেতিবাচক চিন্তা বাদ দিয়ে ভালো কাজে মন দিন।",
        "⏰ সময়ের মূল্য দিন।",
        "📋 আজকের কাজের একটি ছোট তালিকা তৈরি করুন।",
        "🌱 খারাপ অভ্যাসের বদলে ভালো অভ্যাস তৈরি করুন।",
        "💡 প্রতিদিন নতুন কিছু শেখার চেষ্টা করুন।",
    ],

    "islamic": [
        "☪️ আল্লাহকে স্মরণ করুন এবং ভালো কাজ করার চেষ্টা করুন।",
        "🤲 নিজের জন্য ও পরিবারের জন্য দোয়া করুন।",
        "📿 কিছু সময় জিকির ও ইবাদতে দিন।",
        "🕌 নামাজের প্রতি যত্নবান হোন।",
        "🤲 আল্লাহর কাছে নিজের প্রয়োজন ও ভুলের জন্য ক্ষমা চান।",
        "☪️ ভালো কথা বলুন, ভালো কাজ করুন।",
        "📖 কুরআন তিলাওয়াতের জন্য কিছু সময় বের করুন।",
        "❤️ মানুষের সঙ্গে ভালো আচরণ করুন—এটিও সুন্দর আমল।",
        "🤲 আল্লাহর নেয়ামতের জন্য শুকরিয়া আদায় করুন।",
        "🕌 নামাজ সময়মতো আদায় করার চেষ্টা করুন।",
    ],
}


MESSAGE_ENDINGS = [
    "❤️ নিজের যত্ন নিন।",
    "🌸 সুন্দরভাবে দিনটি কাটান।",
    "💙 ভালো থাকুন।",
    "✨ আল্লাহ আপনার দিনটি বরকতময় করুন।",
    "🌿 শান্ত থাকুন এবং ভালো কাজ করুন।",
    "🤍 নিজের প্রতি যত্নশীল হোন।",
    "🌟 আজকের দিনটি ভালো কাজে ব্যবহার করুন।",
    "💪 এগিয়ে চলুন।",
    "😊 হাসিমুখে দিন শুরু করুন।",
    "🌻 ইতিবাচক থাকুন।",
]


def build_message_pool():
    """
    Base messages × endings
    = 500+ possible combinations.
    """
    pool = {}

    for category, messages in BASE_MESSAGES.items():
        combinations = []

        for message in messages:
            combinations.append(message)

            for ending in MESSAGE_ENDINGS:
                combinations.append(f"{message}\n{ending}")

        pool[category] = combinations

    return pool


MESSAGE_POOL = build_message_pool()


def get_random_message(category: str) -> str:
    messages = MESSAGE_POOL.get(category)

    if not messages:
        messages = MESSAGE_POOL.get("motivation", [])

    if not messages:
        return "✨ ভালো থাকুন এবং সময়কে কাজে লাগান।"

    history = _message_history.setdefault(category, [])

    available = [m for m in messages if m not in history]

    if not available:
        history.clear()
        available = messages

    message = random.choice(available)

    history.append(message)

    # Keep history small
    if len(history) > 50:
        del history[:-50]

    return message


# ============================================================
# HOURLY MESSAGE
# ============================================================

def get_time_message(now: datetime.datetime) -> str:
    hour = now.strftime("%I").lstrip("0")
    minute = now.strftime("%M")
    ampm = now.strftime("%p")

    if ampm == "AM":
        bangla_ampm = "রাত" if int(hour) < 6 else "সকাল"
    else:
        bangla_ampm = "দুপুর" if int(hour) < 5 else "বিকেল"

        if int(hour) >= 6:
            bangla_ampm = "সন্ধ্যা"

    return (
        f"🕐 এখন সময় {hour}:{minute} বাজে।\n"
        f"⏰ {bangla_ampm}র সময় চলছে।\n"
        f"✨ সময়কে কাজে লাগান এবং আপনার প্রয়োজনীয় কাজটি করে নিন।"
    )


# ============================================================
# PRAYER
# ============================================================

PRAYER_NAMES = {
    "Fajr": "ফজর",
    "Dhuhr": "যোহর",
    "Asr": "আসর",
    "Maghrib": "মাগরিব",
    "Isha": "এশা",
}


PRAYER_BENEFITS = {
    "Fajr": "দিনের শুরু আল্লাহর ইবাদত দিয়ে করুন।",
    "Dhuhr": "ব্যস্ততার মাঝেও নামাজের জন্য সময় বের করুন।",
    "Asr": "দিনের ব্যস্ততার মাঝেও আল্লাহকে স্মরণ করুন।",
    "Maghrib": "সন্ধ্যার শুরুতে নামাজ আদায় করুন।",
    "Isha": "দিনের শেষ ইবাদতের মাধ্যমে সুন্দর করুন।",
}


def make_prayer_message(prayer_key: str) -> str:
    name = PRAYER_NAMES.get(prayer_key, prayer_key)
    benefit = PRAYER_BENEFITS.get(
        prayer_key,
        "নামাজ মুমিনের জন্য অত্যন্ত গুরুত্বপূর্ণ ইবাদত।"
    )

    return (
        f"🕌 **{name} নামাজের সময় হয়েছে।**\n\n"
        f"⏰ এখন নামাজ আদায়ের সময়।\n"
        f"🤲 দয়া করে নামাজ আদায় করুন।\n"
        f"🌙 {benefit}\n\n"
        f"❤️ আল্লাহ আমাদের সবাইকে নামাজ কায়েম করার তাওফিক দিন। আমিন।"
    )


# ============================================================
# DATABASE USERS
# ============================================================

async def get_all_users():
    """
    Database থেকে সব registered User নিয়ে আসে।
    Render restart হলেও User ID হারাবে না।
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.user_id)
        )
        return [int(row[0]) for row in result.all()]


async def get_user(user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalars().first()


# ============================================================
# SAFE SEND
# ============================================================

async def safe_send(
    bot: Bot,
    user_id: int,
    message: str,
):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        return True

    except Exception as e:
        print(f"[REMINDER] Could not send to {user_id}: {e}")
        return False


# ============================================================
# HOURLY
# ============================================================

async def send_hourly_time(bot: Bot):
    users = await get_all_users()

    now = datetime.datetime.now(TZ)

    # Only at minute 00
    if now.minute != 0:
        return

    hour_key = now.strftime("%Y-%m-%d-%H")

    if _last_hour_sent.get("global") == hour_key:
        return

    _last_hour_sent["global"] = hour_key

    message = get_time_message(now)

    for user_id in users:

        try:
            user = await get_user(user_id)

            if not user:
                continue

            if not user.hourly_notify:
                continue

            await safe_send(
                bot,
                user_id,
                message,
            )

            await asyncio.sleep(0.05)

        except Exception as e:
            print(
                f"[HOURLY] User {user_id} error: {e}"
            )


# ============================================================
# PRAYER CACHE
# ============================================================

_prayer_cache = {}


async def get_cached_prayer_times(city: str):
    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")

    cache_key = f"{city}:{today}"

    cached = _prayer_cache.get(cache_key)

    if cached:
        return cached

    times = await get_prayer_times(
        city=city,
        country="Bangladesh",
    )

    if times:
        _prayer_cache[cache_key] = times

    return times


# ============================================================
# PRAYER REMINDERS
# ============================================================

async def send_prayer_reminders(bot: Bot):
    users = await get_all_users()

    now = datetime.datetime.now(TZ)
    current_time = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    for user_id in users:

        try:
            user = await get_user(user_id)

            if not user:
                continue

            if not user.prayer_notify:
                continue

            city = user.city or "Dhaka"

            prayer_times = await get_cached_prayer_times(city)

            if not prayer_times:
                continue

            for prayer_key in (
                "Fajr",
                "Dhuhr",
                "Asr",
                "Maghrib",
                "Isha",
            ):

                prayer_time = prayer_times.get(prayer_key)

                if not prayer_time:
                    continue

                prayer_time = str(prayer_time)[:5]

                if prayer_time != current_time:
                    continue

                unique_key = (
                    f"{user_id}:"
                    f"{today}:"
                    f"{prayer_key}"
                )

                if _last_prayer_sent.get(user_id) == unique_key:
                    continue

                _last_prayer_sent[user_id] = unique_key

                await safe_send(
                    bot,
                    user_id,
                    make_prayer_message(prayer_key),
                )

                await asyncio.sleep(0.05)

        except Exception as e:
            print(
                f"[PRAYER] User {user_id} error: {e}"
            )


# ============================================================
# DAILY SCHEDULE
# ============================================================

DAILY_SCHEDULE = [

    ("06:30", "wake", "wake_notify"),
    ("08:00", "breakfast", "food_notify"),

    ("10:00", "study", "study_notify"),

    ("12:30", "lunch", "food_notify"),

    ("14:30", "bath", "custom_notify"),

    ("16:30", "sports", "play_notify"),

    ("18:30", "evening", "custom_notify"),

    ("20:30", "dinner", "food_notify"),

    ("22:30", "sleep", "sleep_notify"),
]


EXTRA_SCHEDULE = [

    ("07:30", "water", "custom_notify"),

    ("09:30", "habit", "custom_notify"),

    ("11:30", "water", "custom_notify"),

    ("15:30", "water", "custom_notify"),

    ("17:30", "motivation", "custom_notify"),

    ("19:30", "family", "custom_notify"),

    ("21:30", "islamic", "custom_notify"),
]


# ============================================================
# DAILY REMINDERS
# ============================================================

async def send_daily_reminders(bot: Bot):
    users = await get_all_users()

    now = datetime.datetime.now(TZ)

    current_time = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    for user_id in users:

        try:
            user = await get_user(user_id)

            if not user:
                continue

            for schedule_time, category, setting in DAILY_SCHEDULE:

                if schedule_time != current_time:
                    continue

                if not getattr(user, setting, True):
                    continue

                unique_key = (
                    f"{user_id}:"
                    f"{today}:"
                    f"{schedule_time}:"
                    f"{category}"
                )

                if _last_daily_sent.get(user_id) == unique_key:
                    continue

                _last_daily_sent[user_id] = unique_key

                message = get_random_message(category)

                await safe_send(
                    bot,
                    user_id,
                    message,
                )

                await asyncio.sleep(0.05)

        except Exception as e:
            print(
                f"[DAILY] User {user_id} error: {e}"
            )


# ============================================================
# EXTRA REMINDERS
# ============================================================

async def send_extra_reminders(bot: Bot):
    users = await get_all_users()

    now = datetime.datetime.now(TZ)

    current_time = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    for user_id in users:

        try:
            user = await get_user(user_id)

            if not user:
                continue

            for schedule_time, category, setting in EXTRA_SCHEDULE:

                if schedule_time != current_time:
                    continue

                if not getattr(user, setting, True):
                    continue

                unique_key = (
                    f"{user_id}:"
                    f"{today}:"
                    f"{schedule_time}:"
                    f"{category}"
                )

                if _last_extra_sent.get(user_id) == unique_key:
                    continue

                _last_extra_sent[user_id] = unique_key

                message = get_random_message(category)

                await safe_send(
                    bot,
                    user_id,
                    message,
                )

                await asyncio.sleep(0.05)

        except Exception as e:
            print(
                f"[EXTRA] User {user_id} error: {e}"
            )


# ============================================================
# CLEAN OLD MEMORY
# ============================================================

def cleanup_memory():
    """
    অনেক দিন চললে RAM-এ অপ্রয়োজনীয় key জমে না থাকে।
    """

    if len(_last_hour_sent) > 10:
        _last_hour_sent.clear()

    if len(_last_prayer_sent) > 5000:
        _last_prayer_sent.clear()

    if len(_last_daily_sent) > 5000:
        _last_daily_sent.clear()

    if len(_last_extra_sent) > 5000:
        _last_extra_sent.clear()


# ============================================================
# MAIN LOOP
# ============================================================

async def reminder_loop(bot: Bot):

    global _scheduler_running

    print("======================================")
    print(" AUTOMATIC REMINDER SYSTEM STARTED")
    print("======================================")
    print("Persistent database users enabled.")
    print("Users do NOT need to be online.")
    print("500+ message variations enabled.")

    while _scheduler_running:

        try:

            await send_hourly_time(bot)

            await send_prayer_reminders(bot)

            await send_daily_reminders(bot)

            await send_extra_reminders(bot)

            cleanup_memory()

        except asyncio.CancelledError:
            print("[REMINDER] Scheduler cancelled.")
            break

        except Exception as e:
            print(
                f"[REMINDER LOOP ERROR] {e}"
            )

        # Check every 20 seconds
        await asyncio.sleep(20)


# ============================================================
# START
# ============================================================

def start_scheduler(application):

    global _scheduler_task
    global _scheduler_running

    if _scheduler_running:
        print("[REMINDER] Scheduler already running.")
        return

    _scheduler_running = True

    _scheduler_task = asyncio.create_task(
        reminder_loop(application.bot)
    )

    print("[REMINDER] Scheduler task created.")


# ============================================================
# STOP
# ============================================================

async def stop_scheduler():

    global _scheduler_task
    global _scheduler_running

    _scheduler_running = False

    if _scheduler_task:

        _scheduler_task.cancel()

        try:
            await _scheduler_task

        except asyncio.CancelledError:
            pass

        _scheduler_task = None

    print("[REMINDER] Scheduler stopped.")


# ============================================================
# RELOAD
# ============================================================

async def reload_reminders(application):

    await stop_scheduler()

    await asyncio.sleep(1)

    start_scheduler(application)

    print("[REMINDER] Scheduler reloaded.")


# ============================================================
# TEST
# ============================================================

async def test_reminder(
    bot: Bot,
    user_id: int,
):

    message = (
        "🔔 **Automatic Reminder Test**\n\n"
        "✅ আপনার Reminder System ঠিকভাবে কাজ করছে।\n"
        "🤖 এখন থেকে নির্ধারিত সময়ে বট নিজে থেকেই "
        "আপনাকে মেসেজ পাঠাতে পারবে।"
    )

    return await safe_send(
        bot,
        user_id,
        message,
)
