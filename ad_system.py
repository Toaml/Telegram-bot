# ad_system.py
# Telegram Bot Ad System
# Adsterra + Telegram Web App

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import AD_ENABLED


# =========================================================
# AD WEB APP URL
# =========================================================

AD_WEBAPP_URL = "https://toaml.github.io/Telegram-bot/ad.html"


# =========================================================
# GET AD BUTTON
# =========================================================

def get_ad_button(
    custom_title: str = "🔓 OPEN"
):
    """
    Creates the Telegram Web App ad button.
    """

    if not AD_ENABLED:
        return None

    if not AD_WEBAPP_URL:
        return None

    return InlineKeyboardButton(
        text=custom_title,
        web_app=WebAppInfo(
            url=AD_WEBAPP_URL
        )
    )


# =========================================================
# ATTACH AD BUTTON TO KEYBOARD
# =========================================================

def attach_ad_to_keyboard(
    keyboard: InlineKeyboardMarkup = None
) -> InlineKeyboardMarkup:
    """
    Adds the Adsterra Web App button
    to an existing Telegram inline keyboard.
    """

    ad_btn = get_ad_button()

    # Ads disabled
    if not ad_btn:
        return keyboard or InlineKeyboardMarkup([])

    # Existing keyboard থাকলে সেটি preserve করা হবে
    inline_keyboard = (
        list(keyboard.inline_keyboard)
        if keyboard
        else []
    )

    # Ad button আলাদা row-তে থাকবে
    inline_keyboard.append([
        ad_btn
    ])

    return InlineKeyboardMarkup(
        inline_keyboard
    )
