import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, \
    PreCheckoutQuery
import db

router = Router()

# Расценки в Telegram Stars (XTR)
PRICES_STARS = {
    1: 50,
    7: 140,
    30: 340
}

# Расценки в USDT для CryptoBot и XRocket
PRICES_USDT = {
    1: 2.0,
    7: 10.0,
    30: 30.0
}

CRYPTO_BOT_TOKEN = "ВАШ_ТОКЕН_CRYPTO_BOT"
XROCKET_TOKEN = "ВАШ_ТОКЕН_XROCKET"


@router.message(F.text == "💎 Подписка")
@router.callback_query(F.data == "sub_menu")
async def sub_menu(event: Message | CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — 50 ⭐️", callback_data="star_sub_1")],
        [InlineKeyboardButton(text="🔥 1 неделя — 140 ⭐️", callback_data="star_sub_7")],
        [InlineKeyboardButton(text="🚀 1 месяц — 340 ⭐️", callback_data="star_sub_30")],
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT)", callback_data="crypto_sub_30")],
        [InlineKeyboardButton(text="🚀 XRocket (USDT)", callback_data="xrocket_sub_30")]
    ])
    text = "💳 **Выберите тарифный план и способ оплаты:**"

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


# --- 1. СОЗДАНИЕ ИНВОЙСА TELEGRAM STARS ---
@router.callback_query(F.data.startswith("star_sub_"))
async def create_stars_invoice(call: CallbackQuery, bot: Bot):
    days = int(call.data.split("_")[2])
    stars = PRICES_STARS.get(days, 50)

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"Подписка Zenith VK на {days} дн.",
        description=f"Активация доступа к рассылке и VK модулю на {days} дней.",
        payload=f"sub_stars_{days}",
        currency="XTR",
        prices=[LabeledPrice(label=f"Подписка {days} дней", amount=stars)]
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[2])
    db.set_subscription(message.from_user.id, days)
    await message.answer(f"✅ **Оплата прошла успешно!** Подписка активирована на {days} дней.", parse_mode="Markdown")


# --- 2. РЕАЛЬНОЕ СОЗДАНИЕ ИНВОЙСА CRYPTOBOT ---
@router.callback_query(F.data.startswith("crypto_sub_"))
async def create_cryptobot_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    amount = PRICES_USDT.get(days, 30.0)

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
                    invoice_id = data["result"]["invoice_id"]
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить счет", url=pay_url)],
                        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_crypto_{invoice_id}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="sub_menu")]
                    ])
                    await call.message.edit_text(
                        f"✅ **Инвойс CryptoBot успешно создан!**\n\n"
                        f"📦 Срок: **{days} дн.**\n"
                        f"💵 Сумма: **{amount} USDT**\n\n"
                        f"Нажмите кнопку ниже для оплаты:",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                else:
                    await call.answer("❌ Ошибка при создании инвойса в CryptoBot.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка соединения: {str(e)[:50]}", show_alert=True)


# --- 3. РЕАЛЬНОЕ СОЗДАНИЕ ИНВОЙСА XROCKET ---
@router.callback_query(F.data.startswith("xrocket_sub_"))
async def create_xrocket_invoice(call: CallbackQuery):
    days = int(call.data.split("_")[2])
    amount = PRICES_USDT.get(days, 30.0)

    url = "https://pay.xrocket.tg/api/invoice/create"
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}
    payload = {
        "amount": amount,
        "currency": "USDT",
        "description": f"Подписка Zenith VK на {days} дней"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                res_data = data.get("result", data)
                pay_url = res_data.get("link") or res_data.get("payUrl")

                if pay_url:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить через XRocket", url=pay_url)],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="sub_menu")]
                    ])
                    await call.message.edit_text(
                        f"✅ **Инвойс XRocket успешно создан!**\n\n"
                        f"📦 Срок: **{days} дн.**\n"
                        f"💵 Сумма: **{amount} USDT**\n\n"
                        f"Нажмите кнопку ниже для оплаты:",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                else:
                    await call.answer("❌ Ошибка при создании инвойса в XRocket.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка соединения: {str(e)[:50]}", show_alert=True)