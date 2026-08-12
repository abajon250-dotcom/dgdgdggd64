import os
import aiohttp
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка токенов
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")

# Заголовок для обхода блокировок Cloudflare
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


# ==========================================
# CRYPTOBOT PAYMENTS
# ==========================================

async def create_cryptobot_invoice(amount_usdt: float, description: str, payload: str):
    """Создание счета в CryptoBot"""
    if not CRYPTOBOT_TOKEN:
        logger.error("❌ CRYPTOBOT_TOKEN не задан!")
        return None, None

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {**HEADERS, "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
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
    """Проверка статуса оплаты CryptoBot"""
    if not CRYPTOBOT_TOKEN: return False

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {**HEADERS, "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
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


# ==========================================
# XROCKET PAYMENTS
# ==========================================

async def create_xrocket_invoice(amount_usdt: float, description: str, payload: str):
    """Создание счета в XRocket"""
    if not XROCKET_TOKEN:
        logger.error("❌ XROCKET_TOKEN не задан!")
        return None

    # Исправлено: верный URL для создания инвойсов v1
    url = "https://xrocket.exchange"

    # Исправлено: заголовок авторизации называется "Rocket-Pay-Key", а не "Api-Key"
    headers = {
        **HEADERS,
        "Rocket-Pay-Key": XROCKET_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "amount": amount_usdt,
        "currency": "USDT",
        "description": description,
        "payload": payload
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data, timeout=20) as resp:
                raw_resp = await resp.text()

                if "<html" in raw_resp.lower():
                    logger.error("❌ XRocket Cloudflare Block: Запрос заблокирован защитой.")
                    return None

                if resp.status == 200:
                    res = await resp.json()
                    # Исправлено: поле ссылки в объекте инвойса называется "link"
                    return res.get("data", {}).get("link")

                logger.error(f"XRocket API Error {resp.status}: {raw_resp}")
        except Exception as e:
            logger.exception(f"XRocket Connection Error: {e}")
    return None


async def check_xrocket_invoice(invoice_id: str) -> bool:
    """Проверка статуса оплаты XRocket"""
    if not XROCKET_TOKEN: return False

    # Исправлено: верный эндпоинт v1 для получения информации об инвойсе
    url = f"https://xrocket.exchange/{invoice_id}"

    # Исправлено: верный заголовок авторизации "Rocket-Pay-Key"
    headers = {**HEADERS, "Rocket-Pay-Key": XROCKET_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as resp:
                raw_resp = await resp.text()

                if resp.status == 200:
                    res = await resp.json()
                    # Исправлено: успешный статус в XRocket называется "PAID" (капсом)
                    return res.get("data", {}).get("status") == "PAID"

                logger.error(f"XRocket Check Error {resp.status}: {raw_resp}")
        except Exception as e:
            logger.exception(f"XRocket Check Error: {e}")
    return False
