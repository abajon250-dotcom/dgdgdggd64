from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"), InlineKeyboardButton(text="⚙️ Рассылка", callback_data="menu_mailing")],
            [InlineKeyboardButton(text="🔗 ВК Аккаунты", callback_data="menu_vk_accs"), InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_sub")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="menu_help")]
        ]
    )

def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="buy_sub")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ]
    )

def sub_rates_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 Месяц — $5", callback_data="select_sub_1month")],
            [InlineKeyboardButton(text="3 Месяца — $12", callback_data="select_sub_3months")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ]
    )

def payment_methods_kb(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars_{plan}")],
            [InlineKeyboardButton(text="💎 CryptoBot", callback_data=f"pay_crypto_{plan}")],
            [InlineKeyboardButton(text="🚀 XRocket", callback_data=f"pay_xrocket_{plan}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_sub")]
        ]
    )

def check_pay_kb(pay_url: str, invoice_id: str, plan: str, gate: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay_{gate}_{invoice_id}_{plan}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="buy_sub")]
        ]
    )

def mailing_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать/Изменить шаблон", callback_data="create_template")],
            [InlineKeyboardButton(text="🚀 Запустить рассылку", callback_data="start_mailing")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ]
    )