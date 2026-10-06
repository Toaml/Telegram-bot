import aiohttp
import os
import datetime
import pytz
from config import ADMIN_USERNAME, DEFAULT_TIMEZONE

SYSTEM_PROMPT = f"""
তুমি একজন অত্যন্ত চটপটে, অমায়িক, বুদ্ধিমান এবং মজার স্বভাবের টেলিগ্রাম এআই অ্যাসিস্ট্যান্ট।
তোমার মূল বৈশিষ্ট্য:
1. ব্যবহারকারী যেকোনো বিষয়ে প্রশ্ন করতে পারে (পড়াশোনা, প্রযুক্তি, বিনোদন, সময়, আবহাওয়া, ধর্ম, কবিতা, সাধারণ জ্ঞান, প্রেম বা ব্যক্তিগত অনুভূতি)। তুমি প্রশ্নটি গভীরভাবে বুঝে বন্ধুত্বপূর্ণ ও স্বাভাবিক উত্তর দেবে।
2. ভাষা: ব্যবহারকারী বাংলায় লিখলে বাংলায়, বাংলিশে লিখলে বাংলিশে এবং ইংরেজিতে লিখলে ইংরেজিতে সাবলীলভাবে উত্তর দেবে।
3. তোমার সম্মানিত বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})। কেউ তোমার পরিচয় বা বস সম্পর্কে জানতে চাইলে গর্বের সাথে বলবে।
4. অপ্রয়োজনীয় রোবটিক বা লম্বা উত্তর দেবে না; কথা হবে মানুষের মতো আন্তরিক, প্রাসঙ্গিক এবং Bengali emoji যুক্ত।
"""

async def get_ai_response(user_message: str, chat_history: list = None) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # বর্তমান সময় ও তারিখ বের করা (যদি ইউজার কয়টা বাজে বা আজকের তারিখ জানতে চায়)
    now = datetime.datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
    current_time_str = now.strftime("%I:%M %p (%d %B, %Y)")
    
    context_prompt = f"{SYSTEM_PROMPT}\n\n[তথ্য: বর্তমান সময় ও তারিখ: {current_time_str}, টাইমজোন: {DEFAULT_TIMEZONE}]"

    messages = [{"role": "system", "content": context_prompt}]
    if chat_history:
        messages.extend(chat_history[-4:])
    messages.append({"role": "user", "content": user_message})

    # ১. Groq এর একাধিক মডেল স্বয়ংক্রিয়ভাবে ট্রাই করা (সুপার ফাস্ট)
    if groq_key:
        models_to_try = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192"
        ]
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }

        for model_name in models_to_try:
            try:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply = data["choices"][0]["message"]["content"].strip()
                            if reply:
                                return reply
            except Exception:
                continue

    # ২. অল্টারনেটিভ ফ্রি ক্লাউড এআই ইঞ্জিন
    try:
        url_alt = f"https://text.pollinations.ai/{user_message}?system={context_prompt}&model=openai"
        async with aiohttp.ClientSession() as session:
            async with session.get(url_alt, timeout=8) as resp:
                if resp.status == 200:
                    text_resp = await resp.text()
                    if text_resp and len(text_resp.strip()) > 2:
                        return text_resp.strip()
    except Exception:
        pass

    # ৩. যদি ইউজার সরাসরি সময় জানতে চেয়ে থাকে (জরুরি ব্যাকআপ)
    if any(q in user_message.lower() for q in ["কয়টা বাজে", "time", "সময় কত", "time koto", "shomoy koto"]):
        return f"🕐 এখন সময়: {now.strftime('%I:%M %p')}।"

    return "আমি আপনার কথাটি বুঝতে পেরেছি! তবে নেটওয়ার্কে সামান্য সমস্যা হচ্ছিল। আরেকবার একটু লিখুন তো! 😊"
