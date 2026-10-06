import unicodedata
import random
from config import ADMIN_USERNAME

def clean_text(text: str) -> str:
    # মোবাইল কিবোর্ডের অদৃশ্য চিহ্ন ও স্পেস দূর করা
    text = unicodedata.normalize('NFC', text)
    text = text.replace('\u200c', '').replace('\u200d', '').strip().lower()
    return text

def check_smart_reply(text: str) -> str | None:
    t = clean_text(text)

    # ১. বস ও অ্যাডমিন সম্পর্কিত (যেকোনোভাবে বললেই কাজ করবে)
    if any(k in t for k in ["বস কে", "boss ke", "boss", "admin", "মালিক কে", "কার তৈরি", "বানিয়েছে", "তুমার বস", "তোমার বস"]):
        responses = [
            f"TOMAL CHOWDHURY আমার সম্মানিত বস! 😎\nআমার বসের User Name: @{ADMIN_USERNAME}\nবসের কথামতোই চলি ভাই! 😂👑",
            f"TOMAL CHOWDHURY আমার বস! 🔥\nযেকোনো বিষয়ে উনার সাথে যোগাযোগ করতে পারেন: @{ADMIN_USERNAME} 😎"
        ]
        return random.choice(responses)

    # ২. নাম ও পরিচয়
    if any(k in t for k in ["তোমার নাম", "tomar nam", "নাম কি", "তুমি কে", "who are you", "তোমার পরিচয়"]):
        responses = [
            f"আমি আপনার অল-ইন-ওয়ান AI অ্যাসিস্ট্যান্ট! 😎\nআমার বস হলেন TOMAL CHOWDHURY (@{ADMIN_USERNAME})! 👑",
            "আমি একটি স্মার্ট এআই রোবট! আপনার যেকোনো প্রশ্নের উত্তর দিতে আমি প্রস্তুত। 🤖✨"
        ]
        return random.choice(responses)

    # ৩. তুমি কোথায় থাকো
    if any(k in t for k in ["কোথায় থাকো", "kothay thako", "কোথায় থাকিস", "বাড়ি কোথায়", "where do you live"]):
        return f"আমি আমার বসের সাথে ক্লাউডে থাকি 😎\nআমার বসের User Name: @{ADMIN_USERNAME}\nবসের কথামতোই চলি 😂❤️"

    # ৪. সালাম ও শুভেচ্ছা
    if any(k in t for k in ["hi", "hello", "hey", "হাই", "হ্যালো", "সালাম", "আসসালামু আলাইকুম", "assalamu alaikum", "কেমন আছো", "kemon acho", "কেমন আছেন"]):
        responses = [
            "ওয়ালাইকুম আসসালাম! কেমন আছেন? আমি কীভাবে সাহায্য করতে পারি? 😊",
            "হ্যালো! আশা করি দিনটি চমৎকার কাটছে! বলুন কী সাহায্য লাগবে? 🌸",
            "আমি আলহামদুলিল্লাহ্‌ ভালো আছি! আপনি কেমন আছেন? ✨"
        ]
        return random.choice(responses)

    # ৫. অনুভূতি ও ইমোশন
    if any(k in t for k in ["মন খারাপ", "mon kharap", "ভালো লাগছে না", "bhalo lagche na", "sad", "কষ্ট"]):
        return "আরে ভাই 😔 মন খারাপ করে বসে থাকবেন না। একটু হাসুন 😄 আমি আছি তো! ❤️"

    if any(k in t for k in ["প্রেম", "prem", "ভালোবাসা", "valobasha", "love"]):
        return "প্রেম করবেন? 😏 আগে নিজের ঘুম আর Wi-Fi ঠিক করেন ভাই! 😂❤️"

    return None
