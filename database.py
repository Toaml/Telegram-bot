import datetime

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    select,
    update,
    delete,
    func,
)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL, DEFAULT_TIMEZONE


# ============================================================
# DATABASE ENGINE
# ============================================================

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


# ============================================================
# USER MODEL
# ============================================================

class User(Base):
    __tablename__ = "users"

    user_id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    username = Column(
        String(255),
        nullable=True
    )

    first_name = Column(
        String(255),
        nullable=True
    )

    last_name = Column(
        String(255),
        nullable=True
    )

    city = Column(
        String(100),
        default="Dhaka"
    )

    timezone = Column(
        String(100),
        default=DEFAULT_TIMEZONE
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    # ========================================================
    # NOTIFICATION SETTINGS
    # ========================================================

    # নামাজের সময়
    prayer_notify = Column(
        Boolean,
        default=True
    )

    # প্রতি ঘণ্টার সময়
    # নতুন User-এর জন্য ON
    hourly_notify = Column(
        Boolean,
        default=True
    )

    # পড়াশোনা
    study_notify = Column(
        Boolean,
        default=True
    )

    # কাজ
    work_notify = Column(
        Boolean,
        default=True
    )

    # খেলা / শরীরচর্চা
    play_notify = Column(
        Boolean,
        default=True
    )

    # ঘুম
    sleep_notify = Column(
        Boolean,
        default=True
    )

    # ঘুম থেকে ওঠা
    wake_notify = Column(
        Boolean,
        default=True
    )

    # খাবার
    food_notify = Column(
        Boolean,
        default=True
    )

    # অন্যান্য / Custom reminder
    custom_notify = Column(
        Boolean,
        default=True
    )


# ============================================================
# CONTENT MODEL
# ============================================================

class Content(Base):
    __tablename__ = "contents"

    content_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    title = Column(
        String(500),
        nullable=False,
        index=True
    )

    category = Column(
        String(100),
        nullable=False,
        index=True
    )

    file_id = Column(
        String(500),
        nullable=False
    )

    media_type = Column(
        String(50),
        nullable=False
    )  # video, audio, photo, document

    keywords = Column(
        Text,
        nullable=True
    )

    uploader_id = Column(
        BigInteger,
        nullable=False
    )

    views = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )


# ============================================================
# REMINDER MODEL
# ============================================================

class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        ),
        index=True
    )

    reminder_type = Column(
        String(50),
        default="custom"
    )
    # study, work, play, sleep, wake, food, custom

    message = Column(
        Text,
        nullable=False
    )

    schedule_time = Column(
        String(50),
        nullable=False
    )
    # e.g. "07:00", "daily 19:00"

    is_recurring = Column(
        Boolean,
        default=False
    )

    day_of_week = Column(
        String(50),
        nullable=True
    )
    # mon, tue, etc.

    enabled = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )


# ============================================================
# CONTENT REQUEST MODEL
# ============================================================

class ContentRequest(Base):
    __tablename__ = "content_requests"

    request_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        BigInteger,
        nullable=False
    )

    username = Column(
        String(255),
        nullable=True
    )

    query = Column(
        Text,
        nullable=False
    )

    status = Column(
        String(50),
        default="Pending"
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )


# ============================================================
# BOT SETTINGS MODEL
# ============================================================

class BotSettings(Base):
    __tablename__ = "bot_settings"

    key = Column(
        String(100),
        primary_key=True
    )

    value = Column(
        Text,
        nullable=False
    )


# ============================================================
# ONE-TIME MIGRATION
# ============================================================

async def enable_hourly_for_existing_users_once():
    """
    পুরোনো User-দের hourly notification একবার ON করবে।

    গুরুত্বপূর্ণ:
    - শুধু একবার চলবে।
    - BotSettings-এ migration marker রাখা হবে।
    - পরে User নিজে hourly notification OFF করলে
      Bot restart হলেও আবার ON হবে না।
    """

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(BotSettings).where(
                BotSettings.key == "hourly_notify_migration_v1"
            )
        )

        migration_done = result.scalars().first()

        # ইতিমধ্যে migration হয়ে থাকলে কিছু করবে না
        if migration_done:
            return

        # পুরোনো সব User-এর hourly notification ON
        await session.execute(
            update(User).values(
                hourly_notify=True
            )
        )

        # Migration complete marker
        session.add(
            BotSettings(
                key="hourly_notify_migration_v1",
                value="done"
            )
        )

        await session.commit()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

async def init_db():
    """
    Database-এর সব table তৈরি করবে।
    তারপর পুরোনো User-দের hourly notification
    একবার ON করবে।
    """

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    # পুরোনো User-দের জন্য one-time migration
    await enable_hourly_for_existing_users_once()


# ============================================================
# GET OR CREATE USER
# ============================================================

async def get_or_create_user(
    user_id: int,
    username=None,
    first_name=None,
    last_name=None
):
    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.user_id == user_id
            )
        )

        user = result.scalars().first()

        if not user:

            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )

            session.add(user)

            await session.commit()

            await session.refresh(user)

        return user


# ============================================================
# UPDATE USER CITY
# ============================================================

async def update_user_city(
    user_id: int,
    city: str
):
    async with AsyncSessionLocal() as session:

        await session.execute(
            update(User)
            .where(
                User.user_id == user_id
            )
            .values(
                city=city
            )
        )

        await session.commit()


# ============================================================
# TOGGLE USER SETTING
# ============================================================

async def toggle_user_setting(
    user_id: int,
    setting_name: str
) -> bool:

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.user_id == user_id
            )
        )

        user = result.scalars().first()

        if user and hasattr(
            user,
            setting_name
        ):

            current_val = getattr(
                user,
                setting_name
            )

            # None হলে False হিসেবে ধরা হবে
            if current_val is None:
                current_val = False

            new_val = not current_val

            setattr(
                user,
                setting_name,
                new_val
            )

            await session.commit()

            return new_val

        return False
