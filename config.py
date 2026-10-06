import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# TELEGRAM
# =========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
)

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv(
        "ADMIN_ID",
        "0"
    ).split(",")
    if x.strip().isdigit()
]

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "TOMAL_CHOWDHURY"
).replace("@", "")


# =========================================================
# OPENAI
# =========================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-3.5-turbo"
)


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///bot_database.db"
)

if DATABASE_URL.startswith("postgres://"):

    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+asyncpg://",
        1
    )

elif DATABASE_URL.startswith("postgresql://"):

    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1
    )


# =========================================================
# WEATHER
# =========================================================

WEATHER_API_KEY = os.getenv(
    "WEATHER_API_KEY",
    ""
)

DEFAULT_TIMEZONE = os.getenv(
    "DEFAULT_TIMEZONE",
    "Asia/Dhaka"
)


# =========================================================
# ADSTERRA
# =========================================================

ADSTERRA_PUBLISHER_ID = os.getenv(
    "ADSTERRA_PUBLISHER_ID",
    ""
)

ADSTERRA_AD_KEY = os.getenv(
    "ADSTERRA_AD_KEY",
    ""
)

ADSTERRA_ZONE_ID = os.getenv(
    "ADSTERRA_ZONE_ID",
    ""
)

ADSTERRA_SMARTLINK = os.getenv(
    "ADSTERRA_SMARTLINK",
    "https://www.profitableratecpmnetwork.com/vtaddgsm?key=bf49aea0b2b6e72b6d744dc6a9971422"
)

AD_ENABLED = (
    os.getenv(
        "AD_ENABLED",
        "True"
    ).lower()
    == "true"
)


# =========================================================
# RENDER PORT
# =========================================================

PORT = int(
    os.getenv(
        "PORT",
        "8080"
    )
)


# =========================================================
# WEB APP
# =========================================================

WEBAPP_BASE_URL = os.getenv(
    "WEBAPP_BASE_URL",
    "https://telegram-bot-7hr2.onrender.com"
).rstrip("/")
