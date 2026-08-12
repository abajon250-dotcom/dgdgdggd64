import aiohttp
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# ВЕРНУТЫЕ ЕБАНЫЕ РАСЦЕНКИ (дни: стоимость в USDT)
PRICES = {
    1: 2.0,
    7: 10.0,
    30: 30.0
}

# Токен от @CryptoBot (получить у @CryptoBot -> Pay)
CRYPTO_BOT_TOKEN = "ВАШ_ТОКЕН_CRYPTO_BOT"

@router.message(F.text.contains("Подписка"))
@router.callback_query(F.data == "sub_menu")
async def sub_menu(event: Message | CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {days} дней — {price} USDT", callback_data=f"buy_sub_{days}")]
        for days, price in PRICES.items()
    ])
    text = "🛒 **Выберите срок подписки для оплаты через CryptoBot:**"
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("buy_sub_"))
async def create_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    amount = PRICES[days]

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Подписка Zenith VK на {days} дней"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    pay_url = data["result"]["pay_url"]
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить счет", url=pay_url)],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="sub_menu")]
                    ])
                    await call.message.edit_text(
                        f"✅ **Инвойс успешно создан!**\n\n"
                        f"📦 Срок: **{days} дн.**\n"
                        f"💵 Сумма: **{amount} USDT**\n\n"
                        f"Нажмите кнопку ниже для быстрой оплаты:",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                else:
                    await call.answer("❌ Ошибка при создании инвойса в CryptoBot.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка соединения: {str(e)[:50]}", show_alert=True)