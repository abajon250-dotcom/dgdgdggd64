import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")


# --- CRYPTOBOT ---
async def create_cryptobot_invoice(amount_usdt: float, description: str, payload: str):
    if not CRYPTOBOT_TOKEN:
        logger.error("❌ CRYPTOBOT_TOKEN не задан!")
        return None, None

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": description,
        "payload": payload
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data, timeout=15) as resp:
                res = await resp.json()
                if res.get("ok"):
                    return res["result"]["pay_url"], res["result"]["invoice_id"]
                logger.error(f"CryptoBot API Error: {res}")
        except Exception as e:
            logger.exception(f"CryptoBot Connection Error: {e}")
    return None, None


async def check_cryptobot_invoice(invoice_id: int) -> bool:
    if not CRYPTOBOT_TOKEN:
        return False

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {"invoice_ids": [invoice_id]}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data, timeout=15) as resp:
                res = await resp.json()
                if res.get("ok") and res["result"]["items"]:
                    return res["result"]["items"][0]["status"] == "paid"
        except Exception as e:
            logger.exception(f"CryptoBot Check Error: {e}")
    return False