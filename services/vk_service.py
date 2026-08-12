import aiohttp


async def get_account_data(token: str):
    """
    Проверяет валидность и получает: ФИО и количество друзей.
    """
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Получаем ФИО
            url_user = f"https://api.vk.com/method/users.get?access_token={token}&v=5.131"
            async with session.get(url_user) as resp:
                data = await resp.json()
                if "error" in data:
                    return {"valid": False, "name": "Невалид", "friends": 0}

                user = data["response"][0]
                name = f"{user.get('first_name')} {user.get('last_name')}"

            # 2. Получаем количество друзей
            url_friends = f"https://api.vk.com/method/friends.get?access_token={token}&v=5.131"
            async with session.get(url_friends) as resp:
                f_data = await resp.json()
                friends_count = f_data["response"]["count"] if "response" in f_data else 0

            return {"valid": True, "name": name, "friends": friends_count}
        except Exception:
            return {"valid": False, "name": "Ошибка", "friends": 0}