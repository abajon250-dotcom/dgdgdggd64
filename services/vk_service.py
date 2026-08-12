import aiohttp
import logging


async def get_vk_account_info(token: str) -> dict | None:
    """Полная проверка токена: ФИО, дата рождения, друзья, диалоги."""
    url = "https://api.vk.com/method/users.get"
    params = {
        "access_token": token,
        "v": "5.131",
        "fields": "bdate,photo_200"
    }

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Инфа о пользователе
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                if "error" in data or "response" not in data or not data["response"]:
                    return None
                user_data = data["response"][0]

            vk_id = str(user_data["id"])
            full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            bdate = user_data.get('bdate', 'Не указана')
            photo = user_data.get('photo_200')

            # 2. Количество друзей
            friends_count = 0
            friends_list_text = "Список друзей пуст или скрыт."

            friends_url = "https://api.vk.com/method/friends.get"
            friends_params = {
                "access_token": token,
                "v": "5.131",
                "fields": "nickname,domain"
            }
            async with session.get(friends_url, params=friends_params, timeout=10) as resp:
                f_data = await resp.json()
                if "response" in f_data:
                    friends_count = f_data["response"].get("count", 0)
                    items = f_data["response"].get("items", [])

                    lines = []
                    for f in items:
                        name = f"{f.get('first_name', '')} {f.get('last_name', '')}".strip()
                        domain = f.get('domain', f"id{f.get('id')}")
                        lines.append(f"{name} (https://vk.com/{domain})")
                    if lines:
                        friends_list_text = "\n".join(lines)

            # 3. Количество диалогов (бесед/переписок)
            dialogs_count = 0
            dialogs_url = "https://api.vk.com/method/messages.getConversations"
            dialogs_params = {
                "access_token": token,
                "count": 1,
                "v": "5.131"
            }
            async with session.get(dialogs_url, params=dialogs_params, timeout=10) as resp:
                d_data = await resp.json()
                if "response" in d_data:
                    dialogs_count = d_data["response"].get("count", 0)

            return {
                "vk_id": vk_id,
                "full_name": full_name,
                "bdate": bdate,
                "photo": photo,
                "friends_count": friends_count,
                "dialogs_count": dialogs_count,
                "friends_txt": friends_list_text
            }
    except Exception as e:
        logging.error(f"Ошибка VK API: {e}")
        return None


async def send_vk_message(token: str, user_id: int, message: str) -> bool:
    url = "https://api.vk.com/method/messages.send"
    params = {
        "access_token": token,
        "user_id": user_id,
        "message": message,
        "random_id": 0,
        "v": "5.131"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                return "response" in data
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")
        return False