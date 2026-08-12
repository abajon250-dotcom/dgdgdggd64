import asyncio
import random
import aiohttp
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import db

router = Router()

# Официальные данные VK Android для авторизации по логину и паролю
VK_CLIENT_ID = "2274003"
VK_CLIENT_SECRET = "hHbZxrka2uZ6jB1inYsH"


class VKProlivStates(StatesGroup):
    waiting_for_accounts = State()
    waiting_for_message = State()
    waiting_for_delay = State()


# --- ВПОМОГАТЕЛЬНАЯ ПРОВЕРКА ПОДПИСКИ ---
async def check_access(event, user_id: int) -> bool:
    if not db.is_sub_active(user_id):
        sub_end = db.get_sub_end_date(user_id)
        sub_info = f"\n\n<i>Ваша подписка истекла: {sub_end.strftime('%d.%m.%Y %H:%M:%S')}</i>" if sub_end else ""
        text = (
            "❌ <b>Доступ ограничен!</b>\n\n"
            "Для использования функций VK пролива требуется активная подписка."
            f"{sub_info}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="buy_subscription")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="vk_menu")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return False
    return True


# --- 1. ГЛАВНОЕ МЕНЮ VK ---
@router.message(F.text == "⚙️ VK Аккаунты")
async def text_vk_menu(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id):
        return
    await state.set_state(None)
    await show_main_menu(message, state)


@router.callback_query(F.data == "vk_menu")
async def callback_vk_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await call.answer()
    await show_main_menu(call.message, state, is_edit=True)


async def show_main_menu(message_obj: Message, state: FSMContext, is_edit: bool = False):
    data = await state.get_data()
    acc_count = len(data.get("valid_accounts", []))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Загрузить аккаунты (Токены / Логин:Пароль)", callback_data="vk_upload_accounts")],
        [InlineKeyboardButton(text=f"🛠 Запустить пролив ({acc_count} акк.)", callback_data="vk_start_proliv")],
        [InlineKeyboardButton(text="🗑 Очистить список аккаунтов", callback_data="vk_clear_accounts")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="vk_stats")]
    ])
    text = (
        f"🤖 <b>Панель управления VK и проливом:</b>\n\n"
        f"📦 Аккаунтов в текущей сессии: <b>{acc_count} шт.</b>"
    )
    if is_edit:
        await message_obj.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_obj.answer(text, reply_markup=keyboard, parse_mode="HTML")


# Очистка базы аккаунтов из сессии
@router.callback_query(F.data == "vk_clear_accounts")
async def clear_accounts_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Список загруженных аккаунтов очищен!", show_alert=True)
    await show_main_menu(call.message, state, is_edit=True)


# --- 2. ЕДИНАЯ ЗАГРУЗКА (ТОКЕНЫ + ЛОГИН:ПАРОЛЬ) ---
@router.callback_query(F.data == "vk_upload_accounts")
async def upload_accounts_prompt(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id):
        return
    await call.answer()
    await state.set_state(VKProlivStates.waiting_for_accounts)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]])
    await call.message.edit_text(
        "📥 <b>Массовая загрузка VK аккаунтов:</b>\n\n"
        "Отправьте одним сообщением или файлом <code>.txt</code> список аккаунтов.\n\n"
        "Форматы строк в одной пачке могут быть перемешаны:\n"
        "• <code>vk1.a.token...</code> (готовый токен)\n"
        "• <code>79991234567:password</code> (логин:пароль)",
        reply_markup=keyboard, parse_mode="HTML"
    )


@router.message(VKProlivStates.waiting_for_accounts)
async def process_accounts_batch(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id):
        return

    raw_lines = []
    if message.document:
        if not message.document.file_name.endswith(".txt"):
            return await message.answer("❌ Пожалуйста, отправьте файл в формате <code>.txt</code>.", parse_mode="HTML")
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        raw_lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
    elif message.text:
        raw_lines = message.text.splitlines()
    else:
        return await message.answer("❌ Отправьте текст с аккаунтами или .txt файл!")

    lines = [line.strip() for line in raw_lines if line.strip()]
    if not lines:
        return await message.answer("❌ Список пустой. Попробуйте еще раз.")

    status_msg = await message.answer(f"🔄 Обрабатываю и проверяю {len(lines)} аккаунтов...")
    valid_accounts = []
    invalid_count = 0

    async with aiohttp.ClientSession() as session:
        for line in lines:
            token = None
            try:
                # Вход по Логину:Паролю или прямая передача токена
                if ":" in line and not line.startswith("vk1.a"):
                    login, password = line.split(":", 1)
                    auth_url = "https://oauth.vk.com/token"
                    auth_params = {
                        "grant_type": "password",
                        "client_id": VK_CLIENT_ID,
                        "client_secret": VK_CLIENT_SECRET,
                        "username": login.strip(),
                        "password": password.strip(),
                        "v": "5.131"
                    }
                    async with session.get(auth_url, params=auth_params, timeout=5) as auth_resp:
                        auth_data = await auth_resp.json()
                        if "access_token" in auth_data:
                            token = auth_data["access_token"]
                        else:
                            invalid_count += 1
                            continue
                else:
                    token = line

                # Проверка профиля
                profile_url = f"https://api.vk.com/method/account.getProfileInfo?access_token={token}&v=5.131"
                async with session.get(profile_url, timeout=4) as resp:
                    p_data = await resp.json()
                    if "response" not in p_data:
                        invalid_count += 1
                        continue
                    first_name = p_data["response"].get("first_name", "Имя")
                    last_name = p_data["response"].get("last_name", "Фамилия")

                # Кол-во друзей
                friends_url = f"https://api.vk.com/method/friends.get?access_token={token}&v=5.131"
                async with session.get(friends_url, timeout=4) as resp:
                    f_data = await resp.json()
                    friends_count = f_data.get("response", {}).get("count", 0)

                # Кол-во диалогов/чатов
                chats_url = f"https://api.vk.com/method/messages.getConversations?count=1&access_token={token}&v=5.131"
                async with session.get(chats_url, timeout=4) as resp:
                    c_data = await resp.json()
                    chats_count = c_data.get("response", {}).get("count", 0)

                valid_accounts.append({
                    "token": token,
                    "name": f"{first_name} {last_name}",
                    "friends": friends_count,
                    "chats": chats_count
                })
            except Exception:
                invalid_count += 1

    data = await state.get_data()
    existing_accounts = data.get("valid_accounts", [])
    existing_accounts.extend(valid_accounts)

    await state.update_data(valid_accounts=existing_accounts)
    await state.set_state(VKProlivStates.waiting_for_message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]])

    accs_preview = ""
    for idx, acc in enumerate(valid_accounts[:5], 1):
        accs_preview += f"{idx}. <b>{acc['name']}</b> | 👥 Друзей: {acc['friends']} | 💬 Чатов: {acc['chats']}\n"
    if len(valid_accounts) > 5:
        accs_preview += f"...и еще новых: {len(valid_accounts) - 5}\n"

    await status_msg.edit_text(
        f"✅ <b>Анализ завершен!</b>\n\n"
        f"🟢 Успешно добавлены: <b>{len(valid_accounts)}</b>\n"
        f"🔴 Невалид / Ошибки: <b>{invalid_count}</b>\n"
        f"📦 Всего аккаунтов к проливу: <b>{len(existing_accounts)}</b>\n\n"
        f"<b>Примеры из загрузки:</b>\n{accs_preview}\n"
        f"✍️ Теперь отправьте **текст сообщения** для рассылки:",
        reply_markup=keyboard, parse_mode="HTML"
    )


# --- 3. НАСТРОЙКА ПРОЛИВА (ТЕКСТ И КД) ---
@router.callback_query(F.data == "vk_start_proliv")
async def callback_start_proliv(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id):
        return
    await call.answer()
    await start_proliv_flow(call.message, state, is_edit=True)


@router.message(F.text.in_({"🚀 Начать пролив", "🛠 Запустить пролив"}))
async def text_start_proliv(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id):
        return
    await start_proliv_flow(message, state, is_edit=False)


async def start_proliv_flow(message_obj: Message, state: FSMContext, is_edit: bool = False):
    data = await state.get_data()
    accounts = data.get("valid_accounts", [])
    if not accounts:
        text = "❌ <b>База аккаунтов пуста!</b>\n\nСначала загрузите токены или логин:пароль через кнопку ниже."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Загрузить аккаунты", callback_data="vk_upload_accounts")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="vk_menu")]
        ])
        if is_edit:
            return await message_obj.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            return await message_obj.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.set_state(VKProlivStates.waiting_for_message)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]])
    text = f"🚀 <b>Запуск пролива ({len(accounts)} акк.):</b>\n\nОтправьте текст сообщения для рассылки:"
    if is_edit:
        await message_obj.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_obj.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(VKProlivStates.waiting_for_message)
async def get_proliv_text(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id):
        return
    if message.text in ["⚙️ VK Аккаунты", "🚀 Начать пролив", "🛠 Запустить пролив"]:
        return

    await state.update_data(proliv_text=message.text)
    await state.set_state(VKProlivStates.waiting_for_delay)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]])
    await message.answer(
        f"✅ <b>Текст принят:</b>\n<i>{message.text}</i>\n\n"
        f"⏱ Введите **задержку (кд)** в секундах (например: <code>1</code> или <code>1.5</code>):",
        reply_markup=keyboard, parse_mode="HTML"
    )


@router.message(VKProlivStates.waiting_for_delay)
async def get_delay_and_show_targets(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id):
        return
    try:
        delay = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("❌ Введите число (например, 1 или 1.5):")

    await state.update_data(delay=delay)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 По друзьям", callback_data="start_exec_friends")],
        [InlineKeyboardButton(text="💬 По беседам / чатам", callback_data="start_exec_chats")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="vk_menu")]
    ])
    await message.answer(f"⏱ КД: <b>{delay} сек.</b>\n🎯 Выберите аудиторию для рассылки:", reply_markup=keyboard,
                         parse_mode="HTML")


# --- 4. ПРОЦЕСС РАССЫЛКИ С УЛУЧШЕННЫМ ПРОГРЕСС-БАРОМ И ИТОГОВОЙ ШТУКОЙ ---
@router.callback_query(F.data.startswith("start_exec_"))
async def execute_batch_proliv(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id):
        return
    await call.answer()
    data = await state.get_data()
    accounts = data.get("valid_accounts", [])
    text = data.get("proliv_text", "")
    delay = data.get("delay", 1.0)
    target_type = "friends" if "friends" in call.data else "chats"
    target_name = "друзьям" if target_type == "friends" else "беседам"

    if not accounts:
        return await call.message.edit_text("❌ Нет активных аккаунтов!")

    await state.set_state(None)

    start_time = asyncio.get_event_loop().time()
    success_sent = 0
    fail_count = 0
    total = len(accounts)

    progress_msg = await call.message.edit_text(
        f"🚀 <b>Рассылка запущенна ({target_name})...</b>\n"
        f"📦 Всего аккаунтов: <b>{total}</b>\n\n"
        f"▒▒▒▒▒▒▒▒▒▒ 0% [0 / {total}]\n\n"
        f"✅ Успешно: <code>0</code> | ❌ Ошибок: <code>0</code>",
        parse_mode="HTML"
    )

    async with aiohttp.ClientSession() as session:
        for i, acc in enumerate(accounts, 1):
            token = acc["token"]
            try:
                recipients = []
                if target_type == "friends":
                    get_url = f"https://api.vk.com/method/friends.get?access_token={token}&v=5.131"
                    async with session.get(get_url, timeout=5) as resp:
                        res = await resp.json()
                        recipients = res.get("response", {}).get("items", [])
                else:
                    get_url = f"https://api.vk.com/method/messages.getConversations?count=20&access_token={token}&v=5.131"
                    async with session.get(get_url, timeout=5) as resp:
                        res = await resp.json()
                        items = res.get("response", {}).get("items", [])
                        recipients = [item["conversation"]["peer"]["id"] for item in items if "conversation" in item]

                if recipients:
                    peer_id = recipients[0]
                    send_url = "https://api.vk.com/method/messages.send"
                    payload = {
                        "access_token": token,
                        "peer_id": peer_id,
                        "message": text,
                        "random_id": random.randint(1, 2147483647),
                        "v": "5.131"
                    }
                    async with session.post(send_url, data=payload, timeout=5) as send_resp:
                        if "response" in await send_resp.json():
                            success_sent += 1
                        else:
                            fail_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1

            await asyncio.sleep(delay)

            # Плавный прогресс-бар с живой статистикой и таймером
            percent = int((i / total) * 100)
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            elapsed_sec = int(asyncio.get_event_loop().time() - start_time)

            try:
                await progress_msg.edit_text(
                    f"🚀 <b>Выполняется рассылка по {target_name}...</b>\n\n"
                    f"{bar} <b>{percent}%</b> [{i} / {total}]\n\n"
                    f"✅ Успешно: <code>{success_sent}</code> | ❌ Ошибок: <code>{fail_count}</code>\n"
                    f"⏱ Прошло времени: <code>{elapsed_sec} сек.</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    # ИТОГОВАЯ «ШТУКА» (КРУТОЙ ИНФОРМАТИВНЫЙ ОТЧЕТ)
    total_time = int(asyncio.get_event_loop().time() - start_time)
    success_rate = round((success_sent / total) * 100, 1) if total > 0 else 0

    summary_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Запустить повторно", callback_data="vk_start_proliv")],
        [InlineKeyboardButton(text="🔙 В меню VK", callback_data="vk_menu")]
    ])

    await progress_msg.edit_text(
        f"📊 <b>Итоги рассылки (Пролив завершен):</b>\n\n"
        f"🎯 Аудитория: <b>{target_name}</b>\n"
        f"📦 Всего аккаунтов обработано: <b>{total}</b>\n"
        f"✅ Успешно отправлено: <b>{success_sent}</b>\n"
        f"❌ Ошибок / Сбоев: <b>{fail_count}</b>\n"
        f"📈 Конверсия успеха: <b>{success_rate}%</b>\n"
        f"⏱ Затрачено времени: <b>{total_time} сек.</b>",
        reply_markup=summary_keyboard,
        parse_mode="HTML"
    )


# --- 5. СТАТИСТИКА ---
@router.callback_query(F.data == "vk_stats")
async def vk_stats_action(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id):
        return
    await call.answer()
    data = await state.get_data()
    acc_count = len(data.get("valid_accounts", []))
    sub_end = db.get_sub_end_date(call.from_user.id)
    sub_str = sub_end.strftime("%d.%m.%Y %H:%M:%S") if sub_end else "Нет подписки"

    await call.message.edit_text(
        f"📊 <b>Статистика VK модуля:</b>\n\n"
        f"⏳ Подписка активна до: <b>{sub_str}</b>\n"
        f"📦 Аккаунтов загружено в память: <b>{acc_count}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]]),
        parse_mode="HTML"
    )