import aiohttp
import os
import datetime
import pytz
from config import ADMIN_USERNAME, DEFAULT_TIMEZONE

SYSTEM_PROMPT = f"""
তুমি একজন বুদ্ধিমান, বাস্তবসম্মত এবং মজার স্বভাবের টেলিগ্রাম এআই অ্যাসিস্ট্যান্ট।
১. ব্যবহারকারী যা-ই প্রশ্ন করবে, তুমি বন্ধুসুলভ ও স্বাভাবিকভাবে উত্তর দেবে।
২. বাংলা, বাংলিশ এবং ইংরেজিতে চমৎকার কথা বলতে পারো।
৩. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})।
"""

async def get_ai_response(user_message: str, chat_history: list = None) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    now = datetime.datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
    time_info = now.strftime("%I:%M %p")

    # সরাসরি ঘড়ির সময় জানতে চাইলে কোনো এআই লাগবে না
    if any(q in user_message.lower() for q in ["কয়টা বাজে", "time", "সময় কত"]):
        return f"🕐 এখন সময় রাত/দিন {time_info}।"

    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\nবর্তমান সময়: {time_info}"},
        {"role": "user", "content": user_message}
    ]

    # Groq API ট্রাই করা
    if groq_key:
        models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        for model in models:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": messages, "max_tokens": 450, "temperature": 0.7}
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=7) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["choices"][0]["message"]["content"].strip()
            except Exception:
                continue

    # ব্যাকআপ বুদ্ধিমান উত্তর (যদি এপিআই কোনো কারণে দেরি করে)
    u_lower = user_message.lower()
    if "কেমন আছো" in u_lower:
        return "আমি আলহামদুলিল্লাহ্‌ বেশ ভালো আছি! আপনি কেমন আছেন? 😊"
    elif "নাম কি" in u_lower or "নাম কী" in u_lower:
        return f"আমি আপনার AI অ্যাসিস্ট্যান্ট! আমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME}) 😎"
    elif "তুমি মনে হয় ঠিক করতে পারবা না" in user_message or "পারবা না" in user_message:
        return "আরে ভাই, চেষ্টা করলে সবকিছুই ঠিক করা সম্ভব! আমি আপনার পাশেই আছি, আরেকবার ট্রাই করে দেখুন! 😉💪"

    return "আমি আপনার কথাটি শুনেছি! একটু নেটওয়ার্ক সমস্যার কারণে সংক্ষিপ্ত উত্তর দিচ্ছি। আর কী জানতে চান বলুন? 🌸"
