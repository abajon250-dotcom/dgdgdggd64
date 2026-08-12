import os
import aiohttp

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")


async def create_cryptobot_invoice(amount_usdt: float, description: str, payload: str):
    """Создание инвойса через Crypto Pay API"""
    if not CRYPTOBOT_TOKEN:
        return None, None

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": description,
        "payload": payload,
        "paid_btn_name": "callback",
        "paid_btn_url": "https://t.me/"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as resp:
                res = await resp.json()
                if res.get("ok"):
                    return res["result"]["pay_url"], res["result"]["invoice_id"]
        except Exception as e:
            print(f"CryptoBot Error: {e}")
    return None, None


async def check_cryptobot_invoice(invoice_id: int) -> bool:
    """Проверка статуса оплаты инвойса CryptoBot"""
    if not CRYPTOBOT_TOKEN:
        return False

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {"invoice_ids": [invoice_id]}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as resp:
                res = await resp.json()
                if res.get("ok") and res["result"]["items"]:
                    return res["result"]["items"][0]["status"] == "paid"
        except Exception as e:
            print(f"CryptoBot Check Error: {e}")
    return False


async def create_xrocket_invoice(amount_usdt: float, description: str, payload: str):
    """Создание инвойса через XRocket API"""
    if not XROCKET_TOKEN:
        return None

    url = "https://pay.xrocket.tg/invoice/create"
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}
    data = {
        "amount": amount_usdt,
        "currency": "USDT",
        "description": description,
        "payload": payload
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as resp:
                res = await resp.json()
                if res.get("success") or res.get("ok"):
                    return res["data"]["link"]
        except Exception as e:
            print(f"XRocket Error: {e}")
    return None