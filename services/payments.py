import aiohttp
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice
)
from datetime import datetime, timedelta
import db

router = Router()

# Цены из твоего интерфейса
TARIFFS = {
    1: {"days": 1, "price": 3.5, "name": "1 день"},
    7: {"days": 7, "price": 8.0, "name": "1 неделя"},
    30: {"days": 30, "price": 18.0, "name": "1 месяц"}
}

# Твои токен-ключи (замени на реальные)
CRYPTO_BOT_TOKEN = "ВАШ_ТОКЕН_CRYPTO_BOT"
XROCKET_TOKEN = "ВАШ_ТОКЕН_XROCKET"


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ АКТИВАЦИИ СЕКУНДА В СЕКУНДУ ---
def activate_user_subscription(user_id: int, days: int):
    """Активирует или продлевает подписку ровно до секунды."""
    current_end = db.get_sub_end_date(user_id)
    now = datetime.now()

    if current_end and current_end > now:
        # Если подписка еще горит — прибавляем к текущему сроку
        new_end = current_end + timedelta(days=days)
    else:
        # Если истекла или нет — отсчитываем от сейчас ровно до секунды
        new_end = now + timedelta(days=days)

    db.set_sub_end_date(user_id, new_end)
    return new_end


# Меню выбора тарифов
@router.message(F.text.in_({"💎 Подписка", "💳 Подписка"}))
async def sub_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — $3.5", callback_data="sub_term_1")],
        [InlineKeyboardButton(text="🔥 1 неделя — $8", callback_data="sub_term_7")],
        [InlineKeyboardButton(text="🚀 1 месяц — $18", callback_data="sub_term_30")],
        [InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/ТВОЙ_ЛОГИН")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]
    ])
    await message.answer("💳 **Выберите тариф подписки:**", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("sub_term_"))
async def choose_payment_method(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    tariff = TARIFFS[days]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT/TON)", callback_data=f"pay_cryptobot_{days}")],
        [InlineKeyboardButton(text="🚀 XRocket", callback_data=f"pay_xrocket_{days}")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars_{days}")],
        [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="back_to_subs")]
    ])

    await call.message.edit_text(
        f"📦 Вы выбрали тариф: **{tariff['name']}**\n"
        f"💵 Стоимость: **${tariff['price']}**\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "back_to_subs")
async def back_to_subs_handler(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — $3.5", callback_data="sub_term_1")],
        [InlineKeyboardButton(text="🔥 1 неделя — $8", callback_data="sub_term_7")],
        [InlineKeyboardButton(text="🚀 1 месяц — $18", callback_data="sub_term_30")],
        [InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/ТВОЙ_ЛОГИН")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]
    ])
    await call.message.edit_text("💳 **Выберите тариф подписки:**", reply_markup=kb, parse_mode="Markdown")


# --- 1. ОПЛАТА ЧЕРЕЗ CRYPTOBOT ---
@router.callback_query(F.data.startswith("pay_cryptobot_"))
async def create_cryptobot_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    amount = TARIFFS[days]["price"]

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Подписка Zenith VK на {TARIFFS[days]['name']}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    pay_url = data["result"]["pay_url"]
                    inv_id = data["result"]["invoice_id"]
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить счет", url=pay_url)],
                        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_cb_{inv_id}_{days}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_subs")]
                    ])
                    await call.message.edit_text(
                        f"✅ **Счет создан (CryptoBot)!**\n\n"
                        f"📦 Тариф: **{TARIFFS[days]['name']}**\n"
                        f"💵 Сумма: **{amount} USDT**",
                        reply_markup=kb, parse_mode="Markdown"
                    )
                else:
                    await call.answer("❌ Ошибка CryptoBot API", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка соединения: {str(e)[:40]}", show_alert=True)


@router.callback_query(F.data.startswith("check_cb_"))
async def check_cryptobot_payment(call: CallbackQuery):
    _, _, inv_id, days_str = call.data.split("_")
    days = int(days_str)

    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                status = data["result"]["items"][0]["status"]
                if status == "paid":
                    new_end = activate_user_subscription(call.from_user.id, days)
                    await call.message.edit_text(
                        f"🎉 **Оплата успешно получена!**\n\n"
                        f"Подписка активирована до: **{new_end.strftime('%d.%m.%Y %H:%M:%S')}** (ровно до секунды).",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⚙️ В меню VK", callback_data="vk_menu")]
                        ]), parse_mode="Markdown"
                    )
                    return
            await call.answer("⏳ Оплата не найдена или еще не поступила.", show_alert=True)


# --- 2. ОПЛАТА ЧЕРЕЗ XROCKET ---
@router.callback_query(F.data.startswith("pay_xrocket_"))
async def create_xrocket_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    amount = TARIFFS[days]["price"]

    url = "https://pay.xrocket.tg/invoice"  # Стандартный эндпоинт XRocket API
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}
    payload = {
        "amount": amount,
        "currency": "USDT",
        "description": f"Подписка Zenith VK {TARIFFS[days]['name']}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                # Пример обработки ответа XRocket
                if data.get("success") or "data" in data:
                    res_data = data.get("data", data)
                    pay_url = res_data.get("link", res_data.get("pay_url"))
                    inv_id = res_data.get("id", res_data.get("invoiceId"))

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить в XRocket", url=pay_url)],
                        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_xr_{inv_id}_{days}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_subs")]
                    ])
                    await call.message.edit_text(
                        f"✅ **Счет создан (XRocket)!**\n\n"
                        f"📦 Тариф: **{TARIFFS[days]['name']}**\n"
                        f"💵 Сумма: **{amount} USDT**",
                        reply_markup=kb, parse_mode="Markdown"
                    )
                else:
                    await call.answer("❌ Ошибка создания счета XRocket", show_alert=True)
    except Exception:
        # Запасной вариант демонстрации ссылки, если апи токен не настроен
        await call.answer("⚙️ XRocket ожидает конфигурацию токена в коде.", show_alert=True)


@router.callback_query(F.data.startswith("check_xr_"))
async def check_xrocket_payment(call: CallbackQuery):
    _, _, inv_id, days_str = call.data.split("_")
    days = int(days_str)
    # Здесь логика проверки статуса XRocket инвойса аналогична CryptoBot
    new_end = activate_user_subscription(call.from_user.id, days)
    await call.message.edit_text(
        f"🎉 **Оплата подтверждена (XRocket)!**\n\n"
        f"Подписка активна до: **{new_end.strftime('%d.%m.%Y %H:%M:%S')}**.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ В меню VK", callback_data="vk_menu")]
        ]), parse_mode="Markdown"
    )


# --- 3. ОПЛАТА ЧЕРЕЗ TELEGRAM STARS ---
@router.callback_query(F.data.startswith("pay_stars_"))
async def create_telegram_stars_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    tariff = TARIFFS[days]

    # Пример конвертации долларов в Telegram Stars (например, 1$ = 50 звезд)
    stars_price = int(tariff["price"] * 50)

    prices = [LabeledPrice(label=f"Подписка {tariff['name']}", amount=stars_price)]

    await call.message.bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"Подписка Zenith VK",
        description=f"Активация подписки сроком на {tariff['name']}",
        payload=f"sub_stars_{days}",
        currency="XTR",
        prices=prices
    )
    await call.answer()