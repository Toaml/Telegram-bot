import aiohttp
import os
from config import ADMIN_USERNAME

# Groq API Key (ঐচ্ছিক - ফ্রিতে console.groq.com থেকে নেওয়া যায়)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SYSTEM_PROMPT = f"""
তুমি একজন অত্যন্ত চটপটে, অমায়িক, বুদ্ধিমান এবং মজার স্বভাবের টেলিগ্রাম এআই অ্যাসিস্ট্যান্ট।
নিয়মাবলি:
1. তুমি বাংলা, Banglish এবং English খুব সাবলীলভাবে বোঝো এবং দ্রুত উত্তর দাও।
2. তোমার উত্তর হবে প্রাণবন্ত, স্বাভাবিক এবং প্রয়োজনীয় Bengali ইমোজি যুক্ত।
3. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})। কেউ তোমার পরিচয় বা বস সম্পর্কে জানতে চাইলে তা গর্বের সাথে বলবে।
4. অপ্রয়োজনীয় লম্বা লেকচার দেবে না, সংক্ষেপে কিন্তু আকর্ষণীয়ভাবে উত্তর দেবে।
"""

async def get_ai_response(user_message: str, chat_history: list = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-4:])
    messages.append({"role": "user", "content": user_message})

    # ১. Groq API ব্যবহার (যদি GROQ_API_KEY দেওয়া থাকে - পৃথিবীর সবচেয়ে দ্রুততম এআই)
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # ২. সম্পূর্ণ ফ্রি অল্টারনেটিভ (কোনো API Key ছাড়াই কাজ করবে)
    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": messages,
            "model": "mistral"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=12) as resp:
                if resp.status == 200:
                    text_result = await resp.text()
                    return text_result.strip()
    except Exception:
        pass

    # ৩. শেষ ব্যাকআপ রেসপন্স
    return "আমি আপনার কথাটি বুঝতে পেরেছি! তবে সার্ভারে একটু চাপ থাকায় উত্তর পেতে সামান্য দেরি হচ্ছে। আবার লিখুন তো! 😊"
