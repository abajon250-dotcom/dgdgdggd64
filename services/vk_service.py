import aiohttp
import random

VK_API_VERSION = "5.131"


async def check_vk_account(token: str) -> dict:
    url = "https://api.vk.com/method/users.get"
    params = {
        "access_token": token,
        "v": VK_API_VERSION
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()
                if "response" in data and len(data["response"]) > 0:
                    user_info = data["response"][0]
                    name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

                    # Получаем общее число друзей для статистики
                    friends_count = await get_vk_friends_count_internal(token, session)

                    return {
                        "valid": True,
                        "token": token,
                        "name": name,
                        "friends": friends_count
                    }
    except Exception:
        pass
    return {"valid": False}


async def get_vk_friends_count_internal(token: str, session: aiohttp.ClientSession) -> int:
    url = "https://api.vk.com/method/friends.get"
    params = {
        "access_token": token,
        "v": VK_API_VERSION
    }
    try:
        async with session.get(url, params=params, timeout=10) as response:
            data = await response.json()
            if "response" in data:
                return data["response"].get("count", 0)
    except Exception:
        pass
    return 0


async def get_vk_friends(token: str) -> list:
    """Получает список ID друзей конкретного аккаунта VK"""
    url = "https://api.vk.com/method/friends.get"
    params = {
        "access_token": token,
        "v": VK_API_VERSION
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()
                if "response" in data:
                    return data["response"].get("items", [])
    except Exception:
        pass
    return []


async def send_vk_message(token: str, target: str, text: str) -> dict:
    """Отправляет сообщение пользователю VK по его ID"""
    url = "https://api.vk.com/method/messages.send"
    params = {
        "access_token": token,
        "user_id": target,
        "message": text,
        "random_id": random.randint(1, 2147483647),
        "v": VK_API_VERSION
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=params, timeout=10) as response:
                data = await response.json()
                if "response" in data:
                    return {"success": True}
    except Exception:
        pass
    return {"success": False}