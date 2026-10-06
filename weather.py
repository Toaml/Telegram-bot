import aiohttp
from config import WEATHER_API_KEY

async def get_weather(city: str = "Dhaka") -> str:
    if not city:
        city = "Dhaka"
    
    if WEATHER_API_KEY:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=bn"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        temp = data["main"]["temp"]
                        feels_like = data["main"]["feels_like"]
                        humidity = data["main"]["humidity"]
                        desc = data["weather"][0]["description"]
                        return (
                            f"🌦️ *{city.title()} এর বর্তমান আবহাওয়া:*\n\n"
                            f"🌡️ তাপমাত্রা: *{temp}°C* (অনুভূত হচ্ছে: {feels_like}°C)\n"
                            f"💧 আর্দ্রতা: *{humidity}%*\n"
                            f"☁️ আকাশ: *{desc.capitalize()}*\n\n"
                            f"বাইরে বের হলে সাবধানে থাকুন! 🌈"
                        )
                    else:
                        return f"⚠️ '{city}' শহরের আবহাওয়া তথ্য খুঁজে পাওয়া যায়নি। সঠিক নাম লিখুন।"
        except Exception:
            pass

    # Free Fallback via wttr.in
    try:
        fallback_url = f"https://wttr.in/{city}?format=j1"
        async with aiohttp.ClientSession() as session:
            async with session.get(fallback_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data["current_condition"][0]
                    temp = current["temp_C"]
                    feels = current["FeelsLikeC"]
                    humidity = current["humidity"]
                    desc = current["weatherDesc"][0]["value"]
                    return (
                        f"🌦️ *{city.title()} এর বর্তমান আবহাওয়া:*\n\n"
                        f"🌡️ তাপমাত্রা: *{temp}°C* (Feels like: {feels}°C)\n"
                        f"💧 আর্দ্রতা: *{humidity}%*\n"
                        f"☁️ অবস্থা: *{desc}*\n"
                    )
    except Exception:
        return "⚠️ এই মুহূর্তে আবহাওয়ার তথ্য আনা সম্ভব হচ্ছে না। একটু পর আবার চেষ্টা করুন।"
