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

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    city = Column(String(100), default="Dhaka")
    timezone = Column(String(100), default=DEFAULT_TIMEZONE)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Notification preferences
    prayer_notify = Column(Boolean, default=True)
    hourly_notify = Column(Boolean, default=False)
    study_notify = Column(Boolean, default=True)
    work_notify = Column(Boolean, default=True)
    play_notify = Column(Boolean, default=True)
    sleep_notify = Column(Boolean, default=True)
    wake_notify = Column(Boolean, default=True)
    food_notify = Column(Boolean, default=True)
    custom_notify = Column(Boolean, default=True)


class Content(Base):
    __tablename__ = "contents"

    content_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    file_id = Column(String(500), nullable=False)
    media_type = Column(String(50), nullable=False)  # video, audio, photo, document
    keywords = Column(Text, nullable=True)
    uploader_id = Column(BigInteger, nullable=False)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    reminder_type = Column(
        String(50), default="custom"
    )  # study, work, play, sleep, wake, food, custom
    message = Column(Text, nullable=False)
    schedule_time = Column(String(50), nullable=False)  # e.g., "07:00", "daily 19:00"
    is_recurring = Column(Boolean, default=False)
    day_of_week = Column(String(50), nullable=True)  # mon, tue, etc.
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ContentRequest(Base):
    __tablename__ = "content_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    query = Column(Text, nullable=False)
    status = Column(String(50), default="Pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(user_id: int, username=None, first_name=None, last_name=None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
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


async def update_user_city(user_id: int, city: str):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.user_id == user_id).values(city=city)
        )
        await session.commit()


async def toggle_user_setting(user_id: int, setting_name: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalars().first()
        if user and hasattr(user, setting_name):
            current_val = getattr(user, setting_name)
            new_val = not current_val
            setattr(user, setting_name, new_val)
            await session.commit()
            return new_val
        return False
