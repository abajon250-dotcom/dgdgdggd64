import os
import aiohttp
import logging

# Настройка логирования для отслеживания ошибок платежек в консоли
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")


# ==========================================
# CRYPTO PAY API (CryptoBot)
# ==========================================

async def create_cryptobot_invoice(amount_usdt: float, description: str, payload: str):
    """
    Создание инвойса через Crypto Pay API.
    Возвращает кортеж (pay_url, invoice_id) или (None, None) при ошибке.
    """
    if not CRYPTOBOT_TOKEN:
        logger.error("❌ CRYPTOBOT_TOKEN не задан в .env файле!")
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
            async with session.post(url, headers=headers, json=data, timeout=15) as resp:
                res = await resp.json()
                logger.debug(f"CryptoBot API response: {res}")

                if res.get("ok"):
                    result = res["result"]
                    return result.get("pay_url"), result.get("invoice_id")
                else:
                    logger.error(f"❌ CryptoBot ошибка создания счета: {res}")
        except Exception as e:
            logger.exception(f"❌ CryptoBot ошибка соединения: {e}")

    return None, None


async def check_cryptobot_invoice(invoice_id: int) -> bool:
    """
    Проверка статуса оплаты инвойса в CryptoBot.
    Возвращает True, если счет оплачен, иначе False.
    """
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
                    status = res["result"]["items"][0].get("status")
                    return status == "paid"
        except Exception as e:
            logger.exception(f"❌ CryptoBot ошибка проверки платежа: {e}")

    return False


# ==========================================
# XROCKET PAY API
# ==========================================

async def create_xrocket_invoice(amount_usdt: float, description: str, payload: str):
    token = os.getenv("XROCKET_TOKEN")
    if not token:
        logger.error("❌ XROCKET_TOKEN не найден в .env!")
        return None

    # Исправлено: актуальный рабочий URL для создания инвойсов (Mainnet)
    url = "https://xrocket.exchange"

    headers = {
        "Rocket-Pay-Key": token,
        "Content-Type": "application/json"
    }

    # Поля соответствуют официальной документации xRocket API v1
    data = {
        "amount": amount_usdt,  # Может быть float или str
        "currency": "USDT",
        "description": description,
        "payload": payload
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data, timeout=20) as resp:
                status = resp.status
                raw_resp = await resp.text()

                if status == 200:
                    res = await resp.json()
                    # Исправлено: xRocket возвращает объект инвойса внутри data, а ссылка лежит в поле link
                    return res.get("data", {}).get("link")
                else:
                    logger.error(f"❌ XRocket API ответил ошибкой {status}: {raw_resp}")
                    return None
        except Exception as e:
            logger.exception(f"❌ Ошибка соединения с XRocket: {e}")

    return None


async def check_xrocket_invoice(invoice_id: str) -> bool:
    """
    Проверка статуса инвойса в XRocket.
    """
    if not XROCKET_TOKEN:
        return False

    url = f"https://pay.xrocket.tg/invoice/get?id={invoice_id}"
    headers = {"Rocket-Pay-Key": XROCKET_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as resp:
                res = await resp.json()
                if resp.status == 200 and (res.get("success") or res.get("ok")):
                    status = res.get("data", {}).get("status")
                    return status in ("paid", "Completed", "PAID")
        except Exception as e:
            logger.exception(f"❌ XRocket ошибка проверки платежа: {e}")

    return False