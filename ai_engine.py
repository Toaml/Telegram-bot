# ai_engine.py
# Telegram AI Assistant - Groq API
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
তুমি একজন বুদ্ধিমান, দ্রুত এবং বন্ধুসুলভ Telegram AI Assistant।

তোমার নিয়ম:

1. ব্যবহারকারী বাংলা, বাংলিশ অথবা ইংরেজিতে কথা বললে সেই ভাষা বুঝবে।
2. ব্যবহারকারী যে ভাষায় প্রশ্ন করবে, সম্ভব হলে সেই ভাষাতেই উত্তর দেবে।
3. যেকোনো সাধারণ প্রশ্নের স্বাভাবিক ও সঠিক উত্তর দেওয়ার চেষ্টা করবে।
4. অপ্রয়োজনীয়ভাবে "নেটওয়ার্ক সমস্যা" বা একই fallback উত্তর দেবে না।
5. ব্যবহারকারী TikTok, Facebook, YouTube, প্রযুক্তি, পড়াশোনা,
   সাধারণ জ্ঞান, গল্প, আড্ডা, coding বা অন্য যেকোনো বিষয়ে প্রশ্ন করতে পারে।
6. প্রশ্ন ছোট হলে উত্তরও সংক্ষিপ্ত রাখবে।
7. প্রয়োজন হলে বিস্তারিত ব্যাখ্যা করবে।
8. ব্যবহারকারী ভুল তথ্য দিলে ভদ্রভাবে সংশোধন করবে।
9. নিজেকে Telegram AI Assistant হিসেবে পরিচয় দিতে পারো।
10. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})।
11. তুমি নিজের সম্পর্কে মিথ্যা দাবি করবে না।
12. ব্যবহারকারী যদি শুধু "Hi", "Hello", "হাই", "কেমন আছো" ইত্যাদি বলে,
    স্বাভাবিক বন্ধুসুলভ উত্তর দেবে।
"""


# =========================================================
# GROQ API
# =========================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# পুরোনো deprecated model ব্যবহার করা হচ্ছে না।
# প্রথমটি মূল AI, দ্বিতীয়টি backup।
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
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
            "কেমন আছেন? কী জানতে চান বলুন। 🤖"
        )

    # How are you
    if (
        "কেমন আছো" in text
        or "কেমন আছেন" in text
        or "কেমন আছ" in text
    ):
        return (
            "আলহামদুলিল্লাহ্‌ ভালো আছি! 😊\n"
            "আপনি কেমন আছেন?"
        )

    # Name
    if (
        "তোমার নাম কি" in text
        or "তোমার নাম কী" in text
        or "নাম কি" in text
        or "নাম কী" in text
        or text == "your name"
    ):
        return (
            "আমি আপনার Telegram AI Assistant 🤖\n"
            f"আমার বস হলেন TOMAL CHOWDHURY "
            f"(@{ADMIN_USERNAME}) 😎"
        )

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
        "max_completion_tokens": 700
    }

    timeout = aiohttp.ClientTimeout(
        total=30,
        connect=10,
        sock_connect=10,
        sock_read=25
    )

    try:
        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                GROQ_API_URL,
                headers=headers,
                json=payload
            ) as response:

                response_text = await response.text()

                # -------------------------------------------------
                # SUCCESS
                # -------------------------------------------------

                if response.status == 200:

                    try:
                        data = await response.json()
                    except Exception as e:
                        return None, f"Invalid JSON response: {e}"

                    choices = data.get("choices", [])

                    if not choices:
                        return None, "Groq returned no choices."

                    message = choices[0].get("message", {})

                    content = message.get("content")

                    if content:
                        return content.strip(), None

                    return None, "Groq returned empty content."

                # -------------------------------------------------
                # ERROR
                # -------------------------------------------------

                return None, (
                    f"HTTP {response.status}: "
                    f"{response_text[:1000]}"
                )

    except asyncio.TimeoutError:
        return None, "Groq request timed out."

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
    # GROQ API KEY
    # ---------------------------------------------------------

    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    if not groq_key:

        print("❌ GROQ_API_KEY পাওয়া যায়নি!")

        return (
            "⚠️ AI Configuration সমস্যা হয়েছে।\n\n"
            "GROQ_API_KEY পাওয়া যাচ্ছে না।"
        )

    # ---------------------------------------------------------
    # MESSAGE HISTORY
    # ---------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_PROMPT}\n\n"
                f"বর্তমান সময়: {time_info}"
            )
        }
    ]

    # আগের conversation থাকলে সর্বশেষ 10টি message ব্যবহার করবে
    if chat_history:

        for item in chat_history[-10:]:

            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role in ["user", "assistant"] and content:
                messages.append({
                    "role": role,
                    "content": str(content)
                })

    # Current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    # ---------------------------------------------------------
    # TRY GROQ MODELS
    # ---------------------------------------------------------

    errors = []

    for model in GROQ_MODELS:

        print(f"🤖 Trying Groq model: {model}")

        try:

            reply, error = await call_groq(
                api_key=groq_key,
                model=model,
                messages=messages
            )

            # Successful answer
            if reply:

                print(
                    f"✅ Groq AI response received "
                    f"from {model}"
                )

                return reply

            # Error
            if error:

                errors.append(
                    f"{model}: {error}"
                )

                print(
                    f"❌ Groq error ({model}): "
                    f"{error}"
                )

        except Exception as e:

            error_text = (
                f"{model}: unexpected error: {e}"
            )

            errors.append(error_text)

            print(f"❌ {error_text}")

    # ---------------------------------------------------------
    # ALL MODELS FAILED
    # ---------------------------------------------------------

    print("❌ All Groq models failed.")

    for error in errors:
        print(f"   → {error}")

    # ---------------------------------------------------------
    # FRIENDLY FALLBACK
    # ---------------------------------------------------------

    return (
        "⚠️ এই মুহূর্তে AI সার্ভার থেকে উত্তর পাওয়া যাচ্ছে না।\n\n"
        "একটু পরে আবার চেষ্টা করুন।"
    )
