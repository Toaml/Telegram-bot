import openai
from config import OPENAI_API_KEY, OPENAI_MODEL, ADMIN_USERNAME

openai.api_key = OPENAI_API_KEY

SYSTEM_PROMPT = f"""
তুমি একজন অত্যন্ত বুদ্ধিমান, অমায়িক, সাহায্যকারী এবং মজার স্বভাবের টেলিগ্রাম এআই অ্যাসিস্ট্যান্ট।
তোমার বৈশিষ্ট্য:
1. তুমি বাংলা, Banglish এবং English খুব সুন্দরভাবে বুঝতে ও উত্তর দিতে পারো।
2. তোমার উত্তর হবে সাবলীল, আন্তরিক ও প্রয়োজনীয় ইমোজি সহ।
3. তোমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})। কেউ তোমার পরিচয় বা বস সম্পর্কে জানতে চাইলে গর্বের সাথে তা বলবে।
4. কোনো অযথা বা অপ্রয়োজনীয় লম্বা লেকচার দেবে না। টু-দ্য-পয়েন্ট ও প্রাসঙ্গিক কথা বলবে।
5. ব্যবহারকারীর আবেগ বুঝে সান্ত্বনা বা মোটিভেশন দেবে।
"""

async def get_ai_response(user_message: str, chat_history: list = None) -> str:
    if not OPENAI_API_KEY:
        return "দুঃখিত, আমার এআই ইঞ্জিন এই মুহূর্তে কনফিগার করা নেই। তবে অন্যান্য ফিচারগুলো সচল আছে! 🤖"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-6:])  # কনটেক্সট লিমিট বজায় রাখা
    messages.append({"role": "user", "content": user_message})

    try:
        response = await openai.ChatCompletion.acreate(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "আমি এই মুহূর্তে সংযোগ করতে একটু সমস্যার মুখোমুখি হচ্ছি। অনুগ্রহ করে একটু পর আবার চেষ্টা করুন! ⏳"
