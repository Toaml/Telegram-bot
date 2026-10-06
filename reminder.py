# reminder.py
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
