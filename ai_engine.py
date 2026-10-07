# ai_engine.py
# Telegram AI Assistant - Google Gemini API (100% Free)
# Compatible with handlers.py

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
4. ব্যবহারকারী TikTok, Facebook, YouTube, প্রযুক্তি, পড়াশোনা,
   সাধারণ জ্ঞান, গল্প, আড্ডা, coding বা অন্য যেকোনো বিষয়ে প্রশ্ন করলে বন্ধুসুলভ উত্তর দেবে।
5. প্রশ্ন ছোট হলে উত্তরও সংক্ষিপ্ত রাখবে।
6. প্রয়োজন হলে বিস্তারিত ব্যাখ্যা করবে।
7. ব্যবহারকারী ভুল তথ্য দিলে ভদ্রভাবে সংশোধন করবে।
8. নিজেকে Telegram AI Assistant হিসেবে পরিচয় দেবে।
9. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})।
10. ব্যবহারকারী যদি "Hi", "Hello", "হাই", "কেমন আছো" ইত্যাদি বলে,
    স্বাভাবিক বন্ধুসুলভ উত্তর দেবে।
"""


# =========================================================
# GEMINI API URL
# =========================================================

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


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


# =========================================================
# TIME QUESTION CHECK
# =========================================================

def is_time_question(text: str) -> bool:
    text_lower = text.lower().strip()

    time_questions = [
        "কয়টা বাজে",
        "কয়টা বাজে",
        "এখন কয়টা",
        "এখন কয়টা",
        "সময় কত",
        "সময় কত",
        "এখন সময় কত",
        "এখন সময় কত",
        "what time is it",
        "what is the time",
        "current time",
        "time now",
        "time?"
    ]

    return any(q in text_lower for q in time_questions)


# =========================================================
# SIMPLE LOCAL REPLIES
# =========================================================

def local_reply(user_message: str) -> str | None:
    text = user_message.lower().strip()

    # Greeting
    greetings = [
        "hi",
        "hello",
        "hey",
        "হাই",
        "হ্যালো",
        "আসসালামু আলাইকুম",
        "সালাম"
    ]

    if text in greetings:
        return (
            "ওয়ালাইকুমুস সালাম! 😊\n"
            "কেমন আছেন? বলুন কীভাবে আপনাকে সাহায্য করতে পারি? 🤖"
        )

    # Name
    if text in ["তোমার নাম কি", "তোমার নাম কী", "নাম কি", "নাম কী", "your name"]:
        return (
            "আমি আপনার Telegram AI Assistant 🤖\n"
            f"আমার তৈরি করেছেন TOMAL CHOWDHURY (@{ADMIN_USERNAME}) 😎"
        )

    return None


# =========================================================
# GEMINI REQUEST
# =========================================================

async def call_gemini(
    api_key: str,
    prompt_text: str
) -> tuple[str | None, str | None]:

    url = f"{GEMINI_API_URL}?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{SYSTEM_PROMPT}\n\nবর্তমান সময়: {get_current_time()}\n\nইউজারের প্রশ্ন: {prompt_text}"
                    }
                ]
            }
        ]
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
                url,
                headers=headers,
                json=payload
            ) as response:

                response_text = await response.text()

                if response.status == 200:
                    try:
                        data = await response.json()
                    except Exception as e:
                        return None, f"Invalid JSON response: {e}"

                    candidates = data.get("candidates", [])
                    if not candidates:
                        return None, "Gemini returned no candidates."

                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip(), None

                    return None, "Gemini returned empty text."

                return None, f"HTTP {response.status}: {response_text[:300]}"

    except asyncio.TimeoutError:
        return None, "Gemini request timed out."
    except aiohttp.ClientError as e:
        return None, f"Network error: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"


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

    # ---------------------------------------------------------
    # CURRENT TIME
    # ---------------------------------------------------------
    time_info = get_current_time()

    if is_time_question(user_message):
        return f"🕐 এখন সময় {time_info}।"

    # ---------------------------------------------------------
    # LOCAL QUICK REPLY
    # ---------------------------------------------------------
    quick_reply = local_reply(user_message)
    if quick_reply:
        return quick_reply

    # ---------------------------------------------------------
    # GEMINI API KEY
    # ---------------------------------------------------------
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not gemini_key:
        print("❌ GEMINI_API_KEY পাওয়া যায়নি!")
        return (
            "⚠️ AI Configuration সমস্যা হয়েছে।\n\n"
            "GEMINI_API_KEY পাওয়া যাচ্ছে না। অনুগ্রহ করে Render-এর Environment-এ সেট করুন।"
        )

    # ---------------------------------------------------------
    # CALL GEMINI
    # ---------------------------------------------------------
    reply, error = await call_gemini(
        api_key=gemini_key,
        prompt_text=user_message
    )

    if reply:
        print("✅ Gemini AI response received")
        return reply

    print(f"❌ Gemini Error: {error}")

    return (
        "⚠️ এই মুহূর্তে AI উত্তর দিতে পারছে না।\n\n"
        "অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।"
                )
