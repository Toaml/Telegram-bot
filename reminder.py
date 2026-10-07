# reminder.py
# ============================================================
# Telegram Bot - Automatic Reminder System
# ============================================================
# Features:
# - Automatic hourly time notification
# - Time + Date + Weekday + Temperature + Location
# - Fajr / Dhuhr / Asr / Maghrib / Isha reminders
# - Wake up / Breakfast / Study / Lunch / Bath / Sports
# - Water / Work / Evening / Dinner / Sleep / Family
# - Motivation / Good habits / Islamic reminders
# - 500+ message variations
# - Persistent database users
# - User does not need to be online
# - Render restart friendly
# ============================================================

import asyncio
import datetime
import random
import re
from typing import Optional

import pytz
from telegram import Bot

from sqlalchemy import select

from config import DEFAULT_TIMEZONE
from database import AsyncSessionLocal, User
from prayer import get_prayer_times
from weather import get_weather


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
# DUPLICATE PROTECTION
# ============================================================

_last_hour_sent = set()
_last_prayer_sent = set()
_last_daily_sent = set()
_last_extra_sent = set()
_message_history = {}


# ============================================================
# WEATHER CACHE
# ============================================================

_weather_cache = {}


# ============================================================
# MESSAGE DATABASE
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
        "🌞 আজকের দিনটি নষ্ট করবেন না। সময়মতো উঠে পড়ুন।",
        "🌅 নতুন দিনের শুরুটা হাসিমুখে করুন।",
        "☀️ ঘুম থেকে উঠে কিছুক্ষণ নিজের জন্য সময় দিন।",
        "🌄 সকাল এসেছে। আজকের লক্ষ্যগুলো মনে করুন।",
        "🌞 অলসতা বাদ দিন। আজকের কাজ আজই শুরু করুন।",
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
        "🥚 সকালের খাবার খাওয়ার সময় হয়েছে।",
        "🍎 নিজের শরীরের যত্ন নিতে সময়মতো খাবার খান।",
        "🥣 খালি পেটে বেশি সময় থাকবেন না। নাশতা করে নিন।",
        "🍳 সকালের নাশতা মিস করবেন না।",
        "🍽️ নাশতা করে দিনের কাজ শুরু করুন।",
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
        "📝 মোবাইল কিছুক্ষণ দূরে রেখে পড়াশোনায় মন দিন।",
        "📖 প্রতিদিন একটু একটু করে পড়াশোনা করুন।",
        "🎓 জ্ঞান অর্জনের জন্য আজও কিছু সময় দিন।",
        "🧠 আজ নতুন একটি বিষয় শেখার চেষ্টা করুন।",
        "✍️ মনোযোগ দিয়ে পড়ুন এবং প্রয়োজনীয় বিষয়গুলো লিখে রাখুন।",
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
        "🍚 দুপুরের খাবার খেয়ে শরীরকে প্রয়োজনীয় শক্তি দিন।",
        "🥘 কাজের ব্যস্ততায় খাবার বাদ দেবেন না।",
        "🍽️ লাঞ্চ টাইম! এখন খাবার খেয়ে নিন।",
        "🍛 দুপুর হয়ে গেছে। খাবারের সময় হয়েছে।",
        "🥗 সময়মতো খাবার খাওয়ার অভ্যাস করুন।",
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
        "🚿 শরীর পরিষ্কার-পরিচ্ছন্ন রাখুন।",
        "🧼 এখন একটু ফ্রেশ হয়ে নিন।",
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
        "🏃 শরীরকে সক্রিয় রাখার জন্য কিছুক্ষণ হাঁটুন।",
        "💪 আজকের শরীরচর্চার সময় হয়েছে।",
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
        "💧 আপনার শরীরকে সতেজ রাখতে পানি পান করুন।",
        "🥤 এখন এক গ্লাস পানি পান করার ভালো সময়।",
        "🚰 পানি খাওয়ার কথা মনে আছে তো? এখন পান করুন।",
        "💧 নিয়মিত পানি পান করার অভ্যাস করুন।",
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
        "📋 প্রয়োজনীয় কাজগুলোকে অগ্রাধিকার দিন।",
        "💻 মনোযোগ ধরে রেখে কাজ করুন।",
        "🚀 আপনার লক্ষ্যের দিকে আরও এক ধাপ এগিয়ে যান।",
        "💼 এখন গুরুত্বপূর্ণ কাজটি শুরু করার সময়।",
        "🎯 সময়ের সঠিক ব্যবহার করুন।",
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
        "🌇 দিনের শেষ ভাগটা সুন্দরভাবে কাটান।",
        "🌆 সন্ধ্যায় কাছের মানুষদের একটু সময় দিন।",
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
        "🍽️ ডিনার করে কিছুক্ষণ বিশ্রাম নিন।",
        "🍚 রাতের খাবার বাদ দেবেন না।",
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
        "🛌 শরীর ও মনের বিশ্রামের জন্য ঘুম খুব গুরুত্বপূর্ণ।",
        "😴 আজ অনেক হয়েছে। এবার বিশ্রাম নিন।",
        "🌙 রাত বেশি করবেন না। ঘুমানোর প্রস্তুতি নিন।",
        "🛏️ আগামী দিনের জন্য নিজেকে প্রস্তুত করুন।",
        "😴 শান্তিতে ঘুমান এবং আগামীকাল নতুনভাবে শুরু করুন।",
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
        "🌟 ধৈর্য ধরুন এবং চেষ্টা চালিয়ে যান।",
        "💪 আপনার পরিশ্রম একদিন ফল দেবে।",
        "🚀 আজ একটি ভালো সিদ্ধান্ত নিন।",
        "🔥 নিজের স্বপ্নের জন্য কাজ করুন।",
        "⭐ ছোট পদক্ষেপও আপনাকে সামনে নিয়ে যায়।",
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
        "❤️ বাবা-মায়ের খোঁজ নিন।",
        "👪 পরিবারের সঙ্গে সুন্দর সময় কাটান।",
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
        "📚 প্রতিদিন জ্ঞান অর্জনের চেষ্টা করুন।",
        "⏰ সময় নষ্ট না করে প্রয়োজনীয় কাজ করুন।",
        "🧹 নিজের জায়গা পরিষ্কার রাখার অভ্যাস করুন।",
        "📵 প্রয়োজন ছাড়া ফোন ব্যবহার কমান।",
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
        "🤲 আল্লাহর কাছে দোয়া করতে ভুলবেন না।",
        "🕌 ইবাদতের জন্য কিছু সময় আলাদা রাখুন।",
        "❤️ কাউকে সাহায্য করার চেষ্টা করুন।",
        "📿 কিছু সময় আল্লাহকে স্মরণ করুন।",
        "🤲 আল্লাহ আমাদের সবাইকে ভালো রাখুন। আমিন।",
    ],
}


# ============================================================
# MESSAGE ENDINGS
# ============================================================

MESSAGE_ENDINGS = [
    "",
    "❤️ নিজের যত্ন নিন।",
    "🌸 সুন্দরভাবে দিনটি কাটান।",
    "💙 ভালো থাকুন।",
    "✨ আজকের সময়কে ভালো কাজে ব্যবহার করুন।",
    "🌿 শান্ত থাকুন এবং ভালো কাজ করুন।",
    "🤍 নিজের প্রতি যত্নশীল হোন।",
    "🌟 আজকের দিনটি ভালো কাজে ব্যবহার করুন।",
    "💪 এগিয়ে চলুন।",
    "😊 হাসিমুখে দিনটি কাটান।",
    "🌻 ইতিবাচক থাকুন।",
    "⭐ নিজের লক্ষ্য ভুলবেন না।",
    "💚 সুস্থ থাকুন, ভালো থাকুন।",
    "🤲 আল্লাহ আমাদের সবাইকে ভালো রাখুন।",
    "🌱 প্রতিদিন একটু ভালো হওয়ার চেষ্টা করুন।",
    "❤️ প্রিয় মানুষদের সময় দিন।",
    "⏰ সময়ের মূল্য দিন।",
    "✨ ভালো কাজ চালিয়ে যান।",
    "🌿 নিজের মনকে শান্ত রাখুন।",
    "💫 ছোট ছোট ভালো কাজ চালিয়ে যান।",
    "😊 ভালো থাকুন এবং অন্যকেও ভালো রাখুন।",
    "🌙 আল্লাহ আপনাকে শান্তিতে রাখুন।",
    "🤲 আল্লাহ আপনার মঙ্গল করুন।",
    "⭐ হাল ছাড়বেন না।",
    "💪 চেষ্টা চালিয়ে যান।",
]


# ============================================================
# BUILD MESSAGE POOL
# ============================================================

def build_message_pool():
    pool = {}
    for category, messages in BASE_MESSAGES.items():
        combinations = []
        for message in messages:
            combinations.append(message)
            for ending in MESSAGE_ENDINGS:
                if ending:
                    combinations.append(message + "\n\n" + ending)
        pool[category] = combinations
    return pool


MESSAGE_POOL = build_message_pool()


# ============================================================
# RANDOM MESSAGE
# ============================================================

def get_random_message(category: str) -> str:
    messages = MESSAGE_POOL.get(category)
    if not messages:
        messages = MESSAGE_POOL.get("motivation", [])
    if not messages:
        return "✨ ভালো থাকুন এবং সময়কে কাজে লাগান।"

    history = _message_history.setdefault(category, [])
    available = [message for message in messages if message not in history]

    if not available:
        history.clear()
        available = messages

    message = random.choice(available)
    history.append(message)

    if len(history) > 50:
        del history[:-50]

    return message


# ============================================================
# BANGLA DATE / WEEKDAY
# ============================================================

BANGLA_WEEKDAYS = {
    0: "সোমবার",
    1: "মঙ্গলবার",
    2: "বুধবার",
    3: "বৃহস্পতিবার",
    4: "শুক্রবার",
    5: "শনিবার",
    6: "রবিবার",
}

BANGLA_MONTHS = {
    1: "জানুয়ারি",
    2: "ফেব্রুয়ারি",
    3: "মার্চ",
    4: "এপ্রিল",
    5: "মে",
    6: "জুন",
    7: "জুলাই",
    8: "আগস্ট",
    9: "সেপ্টেম্বর",
    10: "অক্টোবর",
    11: "নভেম্বর",
    12: "ডিসেম্বর",
}


def to_bangla_digits(value) -> str:
    translation = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return str(value).translate(translation)


def get_period(hour: int) -> str:
    if hour == 0 or hour < 6:
        return "রাত"
    if hour < 12:
        return "সকাল"
    if hour == 12 or hour < 17:
        return "দুপুর"
    if hour < 19:
        return "বিকেল"
    return "রাত"


def format_bangla_time(now: datetime.datetime) -> str:
    hour_24 = now.hour
    minute = now.minute

    if hour_24 == 0:
        display_hour = 12
    elif hour_24 > 12:
        display_hour = hour_24 - 12
    else:
        display_hour = hour_24

    period = get_period(hour_24)
    return f"{period} {to_bangla_digits(display_hour)}:{to_bangla_digits(f'{minute:02d}')} মিনিট"


def format_bangla_date(now: datetime.datetime) -> str:
    day = to_bangla_digits(now.day)
    month = BANGLA_MONTHS.get(now.month, str(now.month))
    year = to_bangla_digits(now.year)
    return f"{day} {month} {year}"


# ============================================================
# WEATHER TEMPERATURE
# ============================================================

async def get_temperature_for_city(city: str) -> Optional[str]:
    city = (city or "Dhaka").strip()
    cache_key = city.lower()
    now = datetime.datetime.now(TZ)
    hour_key = now.strftime("%Y-%m-%d-%H")

    cached = _weather_cache.get(cache_key)
    if cached:
        cached_hour, cached_temp = cached
        if cached_hour == hour_key:
            return cached_temp

    try:
        weather_text = await get_weather(city)
        if not weather_text:
            return None

        match = re.search(r"(-?\d+(?:\.\d+)?)\s*°C", weather_text)
        if match:
            temp = match.group(1)
            if temp.endswith(".0"):
                temp = temp[:-2]
            temperature = f"{to_bangla_digits(temp)}°C"
            _weather_cache[cache_key] = (hour_key, temperature)
            return temperature
    except Exception as e:
        print(f"[WEATHER] {city}: {e}")

    return None


# ============================================================
# HOURLY INFORMATION MESSAGE
# ============================================================

async def build_hourly_message(user) -> str:
    city = user.city or "Dhaka"
    user_timezone = getattr(user, "timezone", None) or DEFAULT_TIMEZONE

    try:
        user_tz = pytz.timezone(user_timezone)
    except Exception:
        user_tz = TZ

    now = datetime.datetime.now(user_tz)
    time_text = format_bangla_time(now)
    date_text = format_bangla_date(now)
    weekday_text = BANGLA_WEEKDAYS.get(now.weekday(), "")
    temperature = await get_temperature_for_city(city)

    temperature_text = temperature if temperature else "তথ্য পাওয়া যাচ্ছে না"

    return (
        f"🕐 এখন সময়: {time_text}\n"
        f"📅 তারিখ: {date_text}\n"
        f"📆 বার: {weekday_text}\n"
        f"🌡️ তাপমাত্রা: {temperature_text}\n"
        f"📍 স্থান: {city}\n\n"
        f"⏰ সময়ের মূল্য দিন এবং প্রয়োজনীয় কাজে মনোযোগ দিন।\n"
        f"🌿 নিজের যত্ন নিন এবং ভালো থাকুন।"
    )


# ============================================================
# PRAYER INFORMATION
# ============================================================

PRAYER_NAMES = {
    "Fajr": "ফজর",
    "Dhuhr": "যোহর",
    "Asr": "আসর",
    "Maghrib": "মাগরিব",
    "Isha": "এশা",
}

PRAYER_BENEFITS = {
    "Fajr": "দিনের শুরু আল্লাহর ইবাদত দিয়ে করার সুন্দর সুযোগ।",
    "Dhuhr": "ব্যস্ততার মাঝেও আল্লাহকে স্মরণ করার সময়।",
    "Asr": "দিনের ব্যস্ততার মাঝে নামাজের মাধ্যমে নিজেকে স্মরণ করিয়ে দিন।",
    "Maghrib": "সন্ধ্যার শুরুতে আল্লাহর ইবাদতের সুন্দর সময়।",
    "Isha": "দিনের শেষ নামাজ আদায় করে শান্ত মনে বিশ্রামের প্রস্তুতি নিন।",
}


def make_prayer_message(prayer_key: str, prayer_time: str) -> str:
    name = PRAYER_NAMES.get(prayer_key, prayer_key)
    benefit = PRAYER_BENEFITS.get(prayer_key, "নামাজ মুমিনের জন্য অত্যন্ত গুরুত্বপূর্ণ ইবাদত।")

    return (
        f"🕌 {name} নামাজের সময় হয়েছে!\n\n"
        f"⏰ সময়: {prayer_time}\n\n"
        f"🤲 দয়া করে নামাজ আদায় করুন।\n\n"
        f"🌿 গুরুত্ব: {benefit}\n\n"
        f"❤️ আল্লাহ আমাদের সবাইকে নামাজ কায়েম করার তাওফিক দিন। আমিন।"
    )


# ============================================================
# DATABASE USERS
# ============================================================

async def get_all_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        return result.scalars().all()


# ============================================================
# SAFE SEND
# ============================================================

async def safe_send(bot: Bot, user_id: int, message: str):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        print(f"[REMINDER] Failed to send to {user_id}: {e}")
        return False


# ============================================================
# PRAYER CACHE
# ============================================================

_prayer_cache = {}


async def get_cached_prayer_times(city: str):
    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")
    cache_key = f"{city}:{today}"

    if cache_key in _prayer_cache:
        return _prayer_cache[cache_key]

    try:
        prayer_times = await get_prayer_times(city=city, country="Bangladesh")
        if prayer_times:
            _prayer_cache[cache_key] = prayer_times
            return prayer_times
    except Exception as e:
        print(f"[PRAYER API] {city}: {e}")

    return None


# ============================================================
# PRAYER REMINDERS
# ============================================================

async def send_prayer_reminders(bot: Bot):
    users = await get_all_users()

    for user in users:
        try:
            if not getattr(user, "prayer_notify", True):
                continue

            city = user.city or "Dhaka"
            user_timezone = getattr(user, "timezone", None) or DEFAULT_TIMEZONE

            try:
                user_tz = pytz.timezone(user_timezone)
            except Exception:
                user_tz = TZ

            now = datetime.datetime.now(user_tz)
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            prayer_times = await get_cached_prayer_times(city)
            if not prayer_times:
                continue

            for prayer_key in ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"):
                api_time = prayer_times.get(prayer_key)
                if not api_time:
                    continue

                prayer_time = str(api_time)[:5]
                if prayer_time != current_time:
                    continue

                dedupe_key = (user.user_id, today, prayer_key)
                if dedupe_key in _last_prayer_sent:
                    continue

                message = make_prayer_message(prayer_key, prayer_time)
                success = await safe_send(bot, user.user_id, message)

                if success:
                    _last_prayer_sent.add(dedupe_key)

                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[PRAYER] User {user.user_id} error: {e}")


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
# DAILY REMINDERS
# ============================================================

async def send_daily_reminders(bot: Bot):
    users = await get_all_users()

    for user in users:
        try:
            user_timezone = getattr(user, "timezone", None) or DEFAULT_TIMEZONE

            try:
                user_tz = pytz.timezone(user_timezone)
            except Exception:
                user_tz = TZ

            now = datetime.datetime.now(user_tz)
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            for schedule_time, category, setting in DAILY_SCHEDULE:
                if schedule_time != current_time:
                    continue

                if not getattr(user, setting, True):
                    continue

                dedupe_key = (user.user_id, today, schedule_time, category)
                if dedupe_key in _last_daily_sent:
                    continue

                message = get_random_message(category)
                success = await safe_send(bot, user.user_id, message)

                if success:
                    _last_daily_sent.add(dedupe_key)

                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[DAILY] User {user.user_id} error: {e}")


# ============================================================
# EXTRA REMINDERS
# ============================================================

async def send_extra_reminders(bot: Bot):
    users = await get_all_users()

    for user in users:
        try:
            user_timezone = getattr(user, "timezone", None) or DEFAULT_TIMEZONE

            try:
                user_tz = pytz.timezone(user_timezone)
            except Exception:
                user_tz = TZ

            now = datetime.datetime.now(user_tz)
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            for schedule_time, category, setting in EXTRA_SCHEDULE:
                if schedule_time != current_time:
                    continue

                if not getattr(user, setting, True):
                    continue

                dedupe_key = (user.user_id, today, schedule_time, category)
                if dedupe_key in _last_extra_sent:
                    continue

                message = get_random_message(category)
                success = await safe_send(bot, user.user_id, message)

                if success:
                    _last_extra_sent.add(dedupe_key)

                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[EXTRA] User {user.user_id} error: {e}")


# ============================================================
# HOURLY TIME REMINDER
# ============================================================

async def send_hourly_time(bot: Bot):
    users = await get_all_users()

    for user in users:
        try:
            if not getattr(user, "hourly_notify", True):
                continue

            user_timezone = getattr(user, "timezone", None) or DEFAULT_TIMEZONE

            try:
                user_tz = pytz.timezone(user_timezone)
            except Exception:
                user_tz = TZ

            now = datetime.datetime.now(user_tz)

            # শুধুমাত্র প্রতি ঘণ্টার শুরুতে (০ মিনিটে) পাঠাবে।
            if now.minute != 0:
                continue

            hour_key = f"{user.user_id}:{now.strftime('%Y-%m-%d-%H')}"
            if hour_key in _last_hour_sent:
                continue

            message = await build_hourly_message(user)
            success = await safe_send(bot, user.user_id, message)

            if success:
                _last_hour_sent.add(hour_key)

            await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[HOURLY] User {user.user_id} error: {e}")


# ============================================================
# CLEAN MEMORY
# ============================================================

def cleanup_memory():
    if len(_last_prayer_sent) > 5000:
        _last_prayer_sent.clear()
    if len(_last_daily_sent) > 5000:
        _last_daily_sent.clear()
    if len(_last_extra_sent) > 5000:
        _last_extra_sent.clear()
    if len(_last_hour_sent) > 5000:
        _last_hour_sent.clear()
    if len(_message_history) > 100:
        _message_history.clear()
    if len(_weather_cache) > 500:
        _weather_cache.clear()
    if len(_prayer_cache) > 500:
        _prayer_cache.clear()


# ============================================================
# REMINDER LOOP
# ============================================================

async def reminder_loop(application):
    global _scheduler_running

    try:
        bot = application.bot
        if not bot.initialized:
            await bot.initialize()

        print("[REMINDER] Telegram bot initialized.")
    except Exception as e:
        print(f"[REMINDER] Bot initialization failed: {e}")
        _scheduler_running = False
        return

    print("======================================")
    print(" AUTOMATIC REMINDER SYSTEM STARTED")
    print("======================================")

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
            print(f"[REMINDER] Loop error: {e}")

        # আগের ২০ সেকেন্ডের জায়গায় ৫ সেকেন্ড করা হলো যাতে ১ ঘণ্টার জিরো মিনিট মিস না হয়
        await asyncio.sleep(5)


# ============================================================
# START SCHEDULER
# ============================================================

def start_scheduler(application):
    global _scheduler_task
    global _scheduler_running

    if _scheduler_task is not None and not _scheduler_task.done():
        print("[REMINDER] Scheduler already running.")
        return

    _scheduler_running = True
    _scheduler_task = asyncio.create_task(reminder_loop(application))
    print("[REMINDER] Scheduler task created.")


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
                print(f"[REMINDER] Stop error: {e}")

    _scheduler_task = None
    print("[REMINDER] Scheduler stopped.")


# ============================================================
# RELOAD SCHEDULER
# ============================================================

async def reload_reminders(application_or_bot):
    global _scheduler_task
    global _scheduler_running

    if _scheduler_task is not None:
        if not _scheduler_task.done():
            _scheduler_running = False
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[REMINDER] Reload stop error: {e}")

    _scheduler_task = None
    _scheduler_running = True

    if hasattr(application_or_bot, "bot"):
        application = application_or_bot
    else:
        class ApplicationWrapper:
            def __init__(self, bot):
                self.bot = bot
        application = ApplicationWrapper(application_or_bot)

    _scheduler_task = asyncio.create_task(reminder_loop(application))
    print("[REMINDER] Scheduler reloaded.")


# ============================================================
# TEST REMINDER
# ============================================================

async def test_reminder(bot: Bot, user_id: int):
    message = (
        "🔔 Automatic Reminder Test\n\n"
        "✅ আপনার Automatic Reminder System কাজ করছে।\n\n"
        "🕌 Prayer Reminder\n"
        "🕐 Hourly Time Reminder\n"
        "📅 Date Reminder\n"
        "📆 Weekday Reminder\n"
        "🌡️ Temperature Reminder\n"
        "📍 Location Reminder\n"
        "🌅 Wake Reminder\n"
        "🍳 Breakfast Reminder\n"
        "📚 Study Reminder\n"
        "🍛 Lunch Reminder\n"
        "🚿 Bath Reminder\n"
        "⚽ Sports Reminder\n"
        "💧 Water Reminder\n"
        "💼 Work Reminder\n"
        "🌇 Evening Reminder\n"
        "🍽️ Dinner Reminder\n"
        "😴 Sleep Reminder\n"
        "❤️ Family Reminder\n"
        "💪 Motivation Reminder\n"
        "☪️ Islamic Reminder\n\n"
        "⏰ নির্ধারিত সময়ে বট নিজে থেকেই মেসেজ পাঠাবে।"
    )
    return await safe_send(bot, user_id, message)
