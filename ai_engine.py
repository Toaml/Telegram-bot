import aiohttp
import os
from config import ADMIN_USERNAME

SYSTEM_PROMPT = f"""
তুমি একজন অত্যন্ত চটপটে, অমায়িক, বুদ্ধিমান এবং মজার স্বভাবের টেলিগ্রাম এআই অ্যাসিস্ট্যান্ট।
নিয়মাবলি:
1. তুমি বাংলা, Banglish এবং English খুব সাবলীলভাবে বোঝো এবং দ্রুত উত্তর দাও।
2. তোমার উত্তর হবে প্রাণবন্ত, স্বাভাবিক এবং প্রয়োজনীয় Bengali ইমোজি যুক্ত।
3. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})। কেউ তোমার পরিচয় বা বস সম্পর্কে জানতে চাইলে তা গর্বের সাথে বলবে।
4. অপ্রয়োজনীয় লম্বা লেকচার দেবে না, সংক্ষেপে কিন্তু আকর্ষণীয়ভাবে উত্তর দেবে।
"""

async def get_ai_response(user_message: str, chat_history: list = None) -> str:
    # রানটাইমে সরাসরি কি পড়া এবং স্পেস থাকলে তা কেটে নেওয়া
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-4:])
    messages.append({"role": "user", "content": user_message})

    # ১. Groq API ব্যবহার (সুপার-ফাস্ট Llama 3.1)
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
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
                    else:
                        print(f"Groq API Error: {resp.status}")
        except Exception as e:
            print(f"Groq Request Exception: {e}")

    # ২. ব্যাকআপ ফ্রি এআই
    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": messages,
            "model": "mistral"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    text_result = await resp.text()
                    if text_result.strip():
                        return text_result.strip()
    except Exception:
        pass

    return "আমি আপনার কথাটি বুঝতে পেরেছি! তবে সার্ভারে একটু চাপ থাকায় উত্তর পেতে সামান্য দেরি হচ্ছে। আবার লিখুন তো! 😊"
