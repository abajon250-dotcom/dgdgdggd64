import os
import logging
from curl_cffi.requests import AsyncSession

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка токенов
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")


# Базовые заголовки для авторизации (User-Agent для curl_cffi не обязателен, библиотека ставит его сама под impersonate)
def get_xrocket_headers():
    return {
        "Rocket-Pay-Key": XROCKET_TOKEN,
        "Content-Type": "application/json"
    }


# ==========================================
# XROCKET PAYMENTS (Защищено от Cloudflare)
# ==========================================

async def create_xrocket_invoice(amount_usdt: float, description: str, payload: str):
    """Создание счета в XRocket через браузерную эмуляцию"""
    if not XROCKET_TOKEN:
        logger.error("❌ XROCKET_TOKEN не задан в .env!")
        return None

    url = "https://xrocket.exchange"
    data = {
        "amount": amount_usdt,
        "currency": "USDT",
        "description": description,
        "payload": payload
    }

    # Использованием AsyncSession из curl_cffi с имитацией браузера Chrome
    async with AsyncSession() as session:
        try:
            resp = await session.post(
                url,
                headers=get_xrocket_headers(),
                json=data,
                timeout=20,
                impersonate="chrome120"  # Идеально копирует TLS-отпечаток Chrome 120
            )

            status = resp.status_code
            raw_resp = resp.text

            if status == 200:
                res = resp.json()
                return res.get("data", {}).get("link")

            # Если защита Cloudflare всё-таки пробилась (например, капча)
            if "<html" in raw_resp.lower() or status == 403:
                logger.error(f"❌ XRocket всё ещё блокирует IP сервера (Код {status}). Требуется прокси.")
                return None

            logger.error(f"❌ XRocket API Error {status}: {raw_resp}")

        except Exception as e:
            logger.exception(f"❌ Критическая ошибка соединения с XRocket: {e}")

    return None


async def check_xrocket_invoice(invoice_id: str) -> bool:
    """Проверка статуса оплаты XRocket через браузерную эмуляцию"""
    if not XROCKET_TOKEN: return False

    url = f"https://xrocket.exchange/{invoice_id}"

    async with AsyncSession() as session:
        try:
            resp = await session.get(
                url,
                headers=get_xrocket_headers(),
                timeout=15,
                impersonate="chrome120"
            )

            if resp.status_code == 200:
                res = resp.json()
                return res.get("data", {}).get("status") == "PAID"

            logger.error(f"❌ XRocket Check Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.exception(f"❌ XRocket Check Connection Error: {e}")

    return False
