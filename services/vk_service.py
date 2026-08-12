import aiohttp


async def check_vk_account(token_or_line: str):
    """
    Проверяет валидность токена VK, получает ФИО и количество друзей.
    Поддерживает форматы: токен, login:pass:token
    """
    parts = token_or_line.split(":")
    token = parts[-1].strip()

    if len(token_or_line) > 50 and ":" not in token_or_line:
        token = token_or_line.strip()

    async with aiohttp.ClientSession() as session:
        try:
            # 1. Получаем ФИО через users.get
            url = f"https://api.vk.com/method/users.get?access_token={token}&v=5.131"
            async with session.get(url) as resp:
                data = await resp.json()
                if "error" in data:
                    return {'valid': False, 'name': 'Невалид', 'friends': 0, 'token': token}

                user_info = data["response"][0]
                full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"

            # 2. Получаем количество друзей через friends.get
            url_friends = f"https://api.vk.com/method/friends.get?access_token={token}&v=5.131"
            async with session.get(url_friends) as resp:
                f_data = await resp.json()
                friends_count = 0
                if "response" in f_data:
                    friends_count = f_data["response"].get("count", 0)

            return {'valid': True, 'name': full_name, 'friends': friends_count, 'token': token}
        except Exception:
            return {'valid': False, 'name': 'Ошибка', 'friends': 0, 'token': token}


async def send_vk_message(token: str, target: str, text: str):
    """
    Отправка сообщения через VK API.
    """
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://api.vk.com/method/messages.send"
            params = {
                'access_token': token,
                'v': '5.131',
                'message': text,
                'random_id': 0
            }

            # Определяем получателя ( ID или короткая ссылка )
            if target.isdigit():
                params['user_id'] = target
            else:
                params['domain'] = target.replace('https://vk.com/', '').replace('@', '')

            async with session.post(url, data=params) as resp:
                data = await resp.json()
                if "error" in data:
                    return {"success": False}
                return {"success": True}
        except Exception:
            return {"success": False}