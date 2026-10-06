from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADSTERRA_SMARTLINK, AD_ENABLED

def get_ad_button(custom_title: str = "🌟 Sponsor Link") -> InlineKeyboardButton | None:
    if not AD_ENABLED or not ADSTERRA_SMARTLINK:
        return None
    return InlineKeyboardButton(text=custom_title, url=ADSTERRA_SMARTLINK)

def attach_ad_to_keyboard(keyboard: InlineKeyboardMarkup = None) -> InlineKeyboardMarkup:
    ad_btn = get_ad_button()
    if not ad_btn:
        return keyboard or InlineKeyboardMarkup([])
    
    inline_keyboard = list(keyboard.inline_keyboard) if keyboard else []
    inline_keyboard.append([ad_btn])
    return InlineKeyboardMarkup(inline_keyboard)
