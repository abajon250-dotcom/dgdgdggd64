import os
import aiohttp
from aiogram import Bot
from aiogram.types import LabeledPrice

# Обновленные тарифы и цены
PRICES = {
    "1day": {
        "title": "⚡ 1 день",
        "usd": 2.5,
        "stars": 50,
        "days": 1
    },
    "1week": {
        "title": "🔥 1 неделя",
        "usd": 7.0,
        "stars": 140,
        "days": 7
    },
    "1month": {
        "title": "🚀 1 месяц",
        "usd": 17.0,
        "stars": 340,
        "days": 30
    }
}

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN", "")


async def create_stars_invoice(bot: Bot, user_id: int, plan: str) -> str:
    plan_info = PRICES[plan]
    prices = [LabeledPrice(label=f"Подписка: {plan_info['title']}", amount=plan_info["stars"])]

    title = f"Подписка на бота ({plan_info['title']})"
    description = f"Доступ к системе автоматизации VK на {plan_info['title']}"
    payload = f"sub_{plan}"
    currency = "XTR"

    link = await bot.create_invoice_link(
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency=currency,
        prices=prices
    )
    return link


async def create_cryptobot_invoice(user_id: int, plan: str):
    plan_info = PRICES[plan]
    amount = plan_info["usd"]

    if not CRYPTOBOT_TOKEN:
        return None, None

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Подписка на бота: {plan_info['title']}",
        "payload": f"user_{user_id}_plan_{plan}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    res = await response.json()
                    if res.get("ok"):
                        result = res["result"]
                        return result.get("pay_url"), result.get("invoice_id")
        except Exception:
            pass
    return None, None


async def check_cryptobot_invoice(invoice_id: str) -> bool:
    if not CRYPTOBOT_TOKEN:
        return False

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    res = await response.json()
                    if res.get("ok"):
                        items = res["result"].get("items", [])
                        if items:
                            return items[0].get("status") == "paid"
        except Exception:
            pass
    return False


async def create_xrocket_invoice(user_id: int, plan: str):
    plan_info = PRICES[plan]
    amount = plan_info["usd"]

    if not XROCKET_TOKEN:
        return None, None

    url = "https://pay.xrocket.tg/invoice"
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}
    data = {
        "amount": amount,
        "currency": "USDT",
        "description": f"Подписка: {plan_info['title']}",
        "payload": f"user_{user_id}_plan_{plan}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    res = await response.json()
                    if isinstance(res, dict):
                        data_res = res.get("data", res)
                        return data_res.get("link") or data_res.get("payUrl"), data_res.get("id") or data_res.get(
                            "invoiceId")
        except Exception:
            pass
    return None, None


async def check_xrocket_invoice(invoice_id: str) -> bool:
    if not XROCKET_TOKEN:
        return False

    url = f"https://pay.xrocket.tg/invoice/{invoice_id}"
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    res = await response.json()
                    status = res.get("status") or res.get("data", {}).get("status")
                    return status in ("paid", "completed")
        except Exception:
            pass
    return False