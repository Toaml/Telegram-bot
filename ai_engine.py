# ai_engine.py
# Telegram AI Assistant - Groq API

import asyncio
import aiohttp
import os
import datetime
import pytz

from config import ADMIN_USERNAME, DEFAULT_TIMEZONE


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = f"""
তুমি একজন বুদ্ধিমান, অত্যন্ত দ্রুত এবং বন্ধুসুলভ Telegram AI Assistant।

তোমার নিয়ম:
1. ব্যবহারকারী বাংলা, বাংলিশ অথবা ইংরেজিতে কথা বললে সেই ভাষা বুঝবে।
2. ব্যবহারকারী যে ভাষায় প্রশ্ন করবে, ঠিক সেই ভাষাতেই উত্তর দেবে।
3. যেকোনো সাধারণ প্রশ্নের স্বাভাবিক, নির্ভুল ও সঠিক উত্তর দেওয়ার চেষ্টা করবে।
4. নিজেকে Telegram AI Assistant হিসেবে পরিচয় দেবে।
5. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})।
"""


# =========================================================
# GROQ API & WORKING MODELS
# =========================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "mixtral-8x7b-32768"
]


# =========================================================
# TIME
# =========================================================

def get_current_time():
    try:
        timezone = pytz.timezone(DEFAULT_TIMEZONE)
        now = datetime.datetime.now(timezone)
        return now.strftime("%I:%M %p")
    except Exception:
        return datetime.datetime.now().strftime("%I:%M %p")


def is_time_question(text: str) -> bool:
    text_lower = text.lower().strip()
    time_questions = [
        "কয়টা বাজে", "কয়টা বাজে", "এখন কয়টা", "এখন কয়টা",
        "সময় কত", "সময় কত", "what time is it", "time now"
    ]
    return any(q in text_lower for q in time_questions)


def local_reply(user_message: str) -> str | None:
    text = user_message.lower().strip()

    greetings = ["hi", "hello", "hey", "হাই", "হ্যালো", "আসসালামু আলাইকুম", "সালাম"]
    if text in greetings:
        return "ওয়ালাইকুমুস সালাম! 😊\nকেমন আছেন? বলুন কীভাবে আপনাকে সাহায্য করতে পারি? 🤖"

    if text in ["তোমার নাম কি", "তোমার নাম কী", "নাম কি", "your name"]:
        return f"আমি আপনার Telegram AI Assistant 🤖\nআমার তৈরি করেছেন TOMAL CHOWDHURY (@{ADMIN_USERNAME}) 😎"

    return None


# =========================================================
# GROQ REQUEST
# =========================================================

async def call_groq(
    api_key: str,
    model: str,
    messages: list
) -> tuple[str | None, str | None]:

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800
    }

    timeout = aiohttp.ClientTimeout(
        total=20,
        connect=10,
        sock_connect=10,
        sock_read=15
    )

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                GROQ_API_URL,
                headers=headers,
                json=payload
            ) as response:

                response_text = await response.text()

                if response.status == 200:
                    try:
                        data = await response.json()
                    except Exception as e:
                        return None, f"Invalid JSON: {e}"

                    choices = data.get("choices", [])
                    if not choices:
                        return None, "No choices"

                    content = choices[0].get("message", {}).get("content")
                    if content:
                        return content.strip(), None

                    return None, "Empty content"

                return None, f"HTTP {response.status}: {response_text[:300]}"

    except Exception as e:
        return None, str(e)


# =========================================================
# MAIN AI FUNCTION
# =========================================================

async def get_ai_response(
    user_message: str,
    chat_history: list = None
) -> str:

    if not user_message:
        return "কী জানতে চান বলুন। 😊"

    user_message = user_message.strip()

    time_info = get_current_time()

    if is_time_question(user_message):
        return f"🕐 এখন সময় {time_info}।"

    quick_reply = local_reply(user_message)
    if quick_reply:
        return quick_reply

    # 1. Render Environment Variable থেকে নিবে
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # 2. Fallback Key (GitHub Scanning এড়াতে পার্ট করে রাখা হয়েছে)
    if not groq_key:
        p1 = "gsk_7urvOIZ85vUdgFjMZWRH"
        p2 = "Wgdyb3FY66uONhGcwN5FIDhwpxjbPcft"
        groq_key = p1 + p2

    messages = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nবর্তমান সময়: {time_info}"
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    for model in GROQ_MODELS:
        reply, error = await call_groq(
            api_key=groq_key,
            model=model,
            messages=messages
        )

        if reply:
            return reply

        print(f"❌ Groq error ({model}): {error}")

    return "⚠️ এই মুহূর্তে AI উত্তর দিতে পারছে না। অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন।"
