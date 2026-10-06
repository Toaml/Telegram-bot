import aiohttp

async def get_prayer_times(city: str = "Dhaka", country: str = "Bangladesh") -> dict | None:
    url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    timings = data["data"]["timings"]
                    return {
                        "Fajr": timings["Fajr"],
                        "Sunrise": timings["Sunrise"],
                        "Dhuhr": timings["Dhuhr"],
                        "Asr": timings["Asr"],
                        "Maghrib": timings["Maghrib"],
                        "Isha": timings["Isha"]
                    }
    except Exception:
        return None
    return None
