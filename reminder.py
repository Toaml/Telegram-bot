import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from config import DEFAULT_TIMEZONE
from database import AsyncSessionLocal, Reminder, User
from prayer import get_prayer_times

scheduler = AsyncIOScheduler(timezone=pytz.timezone(DEFAULT_TIMEZONE))

async def send_reminder_job(bot, user_id: int, message: str, reminder_type: str):
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.user_id == user_id))).scalars().first()
        if not user:
            return
        
        # নোটিফিকেশন সেটিংস চেক
        type_field_map = {
            "study": user.study_notify,
            "work": user.work_notify,
            "play": user.play_notify,
            "sleep": user.sleep_notify,
            "wake": user.wake_notify,
            "food": user.food_notify,
            "custom": user.custom_notify
        }
        if not type_field_map.get(reminder_type, True):
            return

    icons = {
        "study": "📚",
        "work": "💼",
        "play": "⚽",
        "sleep": "😴",
        "wake": "🌅",
        "food": "🍽️",
        "custom": "⏰"
    }
    icon = icons.get(reminder_type, "🔔")
    final_text = f"{icon} *রিমাইন্ডার নোটিফিকেশন!*\n\n{message}"
    try:
        await bot.send_message(chat_id=user_id, text=final_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Error sending reminder to {user_id}: {e}")

async def prayer_checker_job(bot):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User).where(User.prayer_notify == True))).scalars().all()
        now_time = datetime.datetime.now(pytz.timezone(DEFAULT_TIMEZONE)).strftime("%H:%M")
        
        # শহরভিত্তিক ক্যাশিং
        city_timings = {}
        for user in users:
            city = user.city or "Dhaka"
            if city not in city_timings:
                city_timings[city] = await get_prayer_times(city=city)
            
            times = city_timings.get(city)
            if not times:
                continue

            for prayer_name, p_time in times.items():
                if p_time == now_time:
                    msg = (
                        f"🕌 *{prayer_name} এর নামাজের সময় হয়েছে ({city})!*\n\n"
                        f"আল্লাহ আমাদের সবাইকে জামাতে ও সঠিক সময়ে নামাজ আদায় করার তৌফিক দান করুন। 🤲"
                    )
                    try:
                        await bot.send_message(chat_id=user.user_id, text=msg, parse_mode="Markdown")
                    except Exception:
                        pass

async def hourly_checker_job(bot):
    now = datetime.datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
    if now.minute == 0:
        time_str = now.strftime("%I:00 %p")
        async with AsyncSessionLocal() as session:
            users = (await session.execute(select(User).where(User.hourly_notify == True))).scalars().all()
            for user in users:
                try:
                    await bot.send_message(chat_id=user.user_id, text=f"🕐 *এখন সময়:* {time_str}")
                except Exception:
                    pass

async def reload_reminders(bot):
    # ডাটাবেস থেকে সব অ্যাক্টিভ রিমাইন্ডার শিডিউলারে রিলোড
    async with AsyncSessionLocal() as session:
        reminders = (await session.execute(select(Reminder).where(Reminder.enabled == True))).scalars().all()
        for rem in reminders:
            try:
                time_parts = rem.schedule_time.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                job_id = f"reminder_{rem.reminder_id}"
                
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)

                scheduler.add_job(
                    send_reminder_job,
                    "cron",
                    hour=hour,
                    minute=minute,
                    args=[bot, rem.user_id, rem.message, rem.reminder_type],
                    id=job_id,
                    replace_existing=True
                )
            except Exception as e:
                print(f"Failed to reload reminder {rem.reminder_id}: {e}")

def start_scheduler(bot):
    # নামাজ ও প্রতি ঘণ্টার চেকার যোগ করা
    scheduler.add_job(prayer_checker_job, "interval", minutes=1, args=[bot], id="prayer_watcher", replace_existing=True)
    scheduler.add_job(hourly_checker_job, "interval", minutes=1, args=[bot], id="hourly_watcher", replace_existing=True)
    if not scheduler.running:
        scheduler.start()
