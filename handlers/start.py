import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import db
from services import payments

router = Router()

CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@ropemu")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]


class VKUploadState(StatesGroup):
    waiting_for_accounts = State()


class AdminGiveSubState(StatesGroup):
    waiting_for_user_id = State()


class AdminRevokeSubState(StatesGroup):
    waiting_for_user_id = State()


class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True


async def send_welcome_menu(message: Message, user_id: int, first_name: str, username: str, bot: Bot):
    try:
        db.add_or_update_user(user_id, username)
    except Exception:
        pass

    # Обязательная проверка подписки на канал для ВСЕХ (включая админов)
    if not await is_subscribed(bot, user_id):
        channel_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_link)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_tg_sub")]
        ])
        return await message.answer(
            "⚠️ <b>Для использования бота необходимо подписаться на наш Telegram-канал!</b>\n\n"
            "Подпишитесь и нажмите кнопку <b>«Я подписался»</b> ниже:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать рассылку")],
            [KeyboardButton(text="🔑 Подключить аккаунты"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="👨‍💻 Админ панель")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"👋 <b>Привет, {first_name}!</b>\n\n"
        f"Добро пожаловать в бот для автоматизации и рассылок VK.\n"
        f"Используйте кнопки меню ниже для навигации:",
        reply_markup=reply_kb,
        parse_mode="HTML"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await send_welcome_menu(
        message=message,
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username,
        bot=bot
    )


# --- КНОПКА: ПРОФИЛЬ ---
@router.message(F.text.contains("Профиль"))
async def profile_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    sub_active = db.is_sub_active(user_id)
    sub_end = db.get_sub_end_date(user_id)

    if sub_active and sub_end:
        sub_status = f"🟢 Активна до: {sub_end.strftime('%d.%m.%Y %H:%M')}"
    elif sub_end:
        sub_status = f"🔴 Истекла: {sub_end.strftime('%d.%m.%Y %H:%M')}"
    else:
        sub_status = "🔴 Отсутствует"

    await message.answer(
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"👤 Username: @{message.from_user.username or 'отсутствует'}\n"
        f"⏳ Статус подписки: {sub_status}\n",
        parse_mode="HTML"
    )


# --- КНОПКА: ПОДПИСКА ---
@router.message(F.text.contains("Подписка"))
async def subscription_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    sub_active = db.is_sub_active(user_id)
    sub_end = db.get_sub_end_date(user_id)

    if sub_active and sub_end:
        sub_status = f"🟢 <b>Активна до:</b> {sub_end.strftime('%d.%m.%Y %H:%M')}"
    else:
        sub_status = "🔴 <b>Отсутствует или истекла</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Выбрать тариф и продлить", callback_data="buy_subscription")]
    ])

    await message.answer(
        f"💳 <b>Управление подпиской</b>\n\n"
        f"⏳ Текущий статус: {sub_status}\n\n"
        f"Нажмите кнопку ниже, чтобы ознакомиться с тарифами:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# --- МЕНЮ: ПОДКЛЮЧИТЬ АККАУНТЫ ---
@router.message(F.text.contains("Подключить аккаунты"))
async def connect_accs_btn(message: Message, state: FSMContext, user_id: int = None):
    await state.clear()
    if not user_id:
        user_id = message.from_user.id

    if not await is_subscribed(message.bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username,
                                       message.bot)

    if not db.is_sub_active(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription")]
        ])
        return await message.answer(
            f"❌ <b>Для подключения аккаунтов необходима активная подписка!</b>\n\n"
            f"Ваш ID: <code>{user_id}</code>\n"
            f"Приобретите подписку в разделе «💳 Подписка» или нажмите кнопку ниже:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    stats = db.get_vk_accounts_stats()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить аккаунты (.txt / текст)", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="📂 Мои аккаунты VK", callback_data="vk_accounts_list")],
        [InlineKeyboardButton(text="❌ Очистить все аккаунты", callback_data="vk_clear_all")]
    ])

    await message.answer(
        f"🔑 <b>Подключение VK аккаунтов</b>\n\n"
        f"📊 <b>Текущие аккаунты в базе:</b>\n"
        f"• Всего загружено: <b>{stats['total']}</b>\n"
        f"• Рабочих (валид): <b>{stats['valid']}</b>\n"
        f"• Ошибок (невалид): <b>{stats['invalid']}</b>\n\n"
        f"Нажмите <b>«➕ Загрузить аккаунты»</b> и отправьте <b>.txt файл</b> или список аккаунтов сообщением.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "connect_accs_menu")
async def back_to_accs_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    await connect_accs_btn(call.message, state, user_id=call.from_user.id)


@router.callback_query(F.data == "vk_accounts_list")
async def show_vk_accounts_list(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    user_id = call.from_user.id

    if not await is_subscribed(bot, user_id):
        return await call.message.edit_text("⚠️ <b>Необходимо подписаться на канал!</b>", parse_mode="HTML")

    if not db.is_sub_active(user_id):
        return await call.message.edit_text("❌ <b>У вас нет активной подписки!</b>", parse_mode="HTML")

    accounts = db.get_user_vk_accounts()
    if not accounts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Загрузить аккаунты (.txt)", callback_data="vk_add_bulk")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
        ])
        return await call.message.edit_text("📂 <b>Список аккаунтов пуст.</b>", reply_markup=keyboard, parse_mode="HTML")

    text = f"📂 <b>Загружено аккаунтов:</b> {len(accounts)}\n\n"
    for acc in accounts[:15]:
        acc_id, acc_data, is_valid = acc
        status = "✅" if is_valid else "❌"
        short_data = acc_data[:20] + "..." if len(acc_data) > 20 else acc_data
        text += f"{status} ID: {acc_id} | <code>{short_data}</code>\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еще (.txt)", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="❌ Очистить все", callback_data="vk_clear_all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
    ])
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "vk_add_bulk")
async def start_add_bulk(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    user_id = call.from_user.id

    if not await is_subscribed(bot, user_id):
        return await call.message.edit_text("⚠️ <b>Необходимо подписаться на канал!</b>", parse_mode="HTML")

    if not db.is_sub_active(user_id):
        return await call.message.edit_text("❌ <b>У вас нет активной подписки!</b>", parse_mode="HTML")

    await state.set_state(VKUploadState.waiting_for_accounts)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="connect_accs_menu")]
    ])

    await call.message.edit_text(
        "📥 <b>Загрузка VK аккаунтов пачками</b>\n\n"
        "Отправьте сюда <b>.txt файл</b> с аккаунтами или отправьте их <b>текстом в сообщении</b> (каждый с новой строки).\n\n"
        "<b>Формат:</b>\n"
        "• <code>login:pass</code>\n"
        "• <code>login:pass:token</code>\n"
        "• <code>token</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(VKUploadState.waiting_for_accounts, F.document | F.text)
async def process_accounts_input(message: Message, state: FSMContext, bot: Bot):
    if not await is_subscribed(bot, message.from_user.id):
        return await message.answer("⚠️ Подпишитесь на канал для продолжения.")

    lines = []
    if message.document:
        if not message.document.file_name.endswith('.txt'):
            return await message.answer("❌ Отправьте файл в формате <b>.txt</b>", parse_mode="HTML")
        file_info = await bot.get_file(message.document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        try:
            content = downloaded_file.read().decode('utf-8')
        except UnicodeDecodeError:
            content = downloaded_file.read().decode('cp1251', errors='ignore')
        lines = content.splitlines()
    elif message.text:
        lines = message.text.splitlines()

    accounts = [line.strip() for line in lines if line.strip()]
    if not accounts:
        return await message.answer("❌ Сообщение или файл не содержат аккаунтов.")

    added, skipped = db.add_vk_accounts_bulk(accounts)
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Посмотреть аккаунты", callback_data="vk_accounts_list")]
    ])

    await message.answer(
        f"✅ <b>Успешно обработано!</b>\n\n"
        f"📥 Добавлено аккаунтов: <b>{added}</b>\n"
        f"⚠️ Пропущено (дубликаты/пустые): <b>{skipped}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "vk_clear_all")
async def clear_all_accs(call: CallbackQuery):
    await call.answer()
    db.clear_all_vk_accounts()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить новые", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
    ])
    await call.message.edit_text("🗑 <b>Все VK аккаунты успешно удалены!</b>", reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text.contains("Начать рассылку"))
async def start_broadcast_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    if not db.is_sub_active(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription")]
        ])
        return await message.answer(
            "❌ <b>Для запуска рассылки необходима активная подписка!</b>\n\n"
            "Приобретите подписку, чтобы получить доступ к функционалу.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    stats = db.get_vk_accounts_stats()
    if stats['valid'] == 0:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Подключить аккаунты", callback_data="vk_add_bulk")]
        ])
        return await message.answer(
            "⚠️ <b>У вас нет рабочих VK аккаунтов!</b>\nСначала подключите аккаунты.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить пролив", callback_data="vk_start_proliv")],
        [InlineKeyboardButton(text="⚙️ Настройки пролива", callback_data="vk_proliv_settings")]
    ])

    await message.answer(
        f"🚀 <b>Запуск пролива / рассылки VK</b>\n\n"
        f"✅ Доступно аккаунтов для пролива: <b>{stats['valid']}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# --- АДМИН-ПАНЕЛЬ ---
@router.message(F.text.contains("Админ панель"))
async def admin_panel_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return await message.answer("❌ <b>У вас нет доступа к админ-панели!</b>", parse_mode="HTML")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_bot_stats")],
        [InlineKeyboardButton(text="⚙️ Статистика VK аккаунтов", callback_data="admin_vk_stats")],
        [InlineKeyboardButton(text="📈 Статистика проливов", callback_data="admin_proliv_stats")],
        [
            InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_sub"),
            InlineKeyboardButton(text="🚫 Забрать подписку", callback_data="admin_revoke_sub")
        ],
        [InlineKeyboardButton(text="📢 Начать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])

    await message.answer(
        "👑 <b>Админ-панель управления:</b>\n\nВыберите нужный раздел ниже:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_bot_stats")
async def admin_bot_stats_callback(call: CallbackQuery, bot: Bot):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    total_users = getattr(db, "get_total_users_count", lambda: len(getattr(db, "get_all_users", lambda: [])()))()
    await call.message.edit_text(
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👥 Всего пользователей в базе: <b>{total_users}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_vk_stats")
async def admin_vk_stats_callback(call: CallbackQuery):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    stats = db.get_vk_accounts_stats()
    await call.message.edit_text(
        f"⚙️ <b>Статистика VK аккаунтов:</b>\n\n"
        f"• Всего загружено: <b>{stats['total']}</b>\n"
        f"• Рабочих (валидных): <b>{stats['valid']}</b>\n"
        f"• Ошибочных (невалидных): <b>{stats['invalid']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_proliv_stats")
async def admin_proliv_stats_callback(call: CallbackQuery):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    await call.message.edit_text(
        "📈 <b>Статистика проливов:</b>\n\n"
        "• Активных задач: <b>0</b>\n"
        "• Успешно завершенных: <b>0</b>\n"
        "• Отправлено сообщений за всё время: <b>0</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_give_sub")
async def admin_give_sub_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(AdminGiveSubState.waiting_for_user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])
    await call.message.edit_text(
        "🎁 <b>Выдача подписки вручную</b>\n\n"
        "Отправьте в чат в формате:\n<code>TELEGRAM_ID ДНИ</code>\n\n"
        "<i>Пример: <code>8805077017 30</code></i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(AdminGiveSubState.waiting_for_user_id, F.text)
async def process_admin_give_sub(message: Message, state: FSMContext):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        days = int(parts[1])

        new_end = db.set_subscription(target_id, days)
        await state.clear()

        await message.answer(
            f"✅ <b>Подписка успешно выдана!</b>\n\n"
            f"👤 User ID: <code>{target_id}</code>\n"
            f"⏳ Активна до: <b>{new_end}</b>",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer("❌ <b>Неверный формат!</b>\nОтправьте в формате: <code>ID ДНИ</code>", parse_mode="HTML")


@router.callback_query(F.data == "admin_revoke_sub")
async def admin_revoke_sub_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(AdminRevokeSubState.waiting_for_user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])
    await call.message.edit_text(
        "🚫 <b>Забрать подписку</b>\n\n"
        "Отправьте Telegram ID пользователя:\n\n"
        "<i>Пример: <code>8805077017</code></i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(AdminRevokeSubState.waiting_for_user_id, F.text)
async def process_admin_revoke_sub(message: Message, state: FSMContext):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        return

    try:
        target_id = int(message.text.strip())
        db.set_subscription(target_id, 0)
        await state.clear()

        await message.answer(
            f"🚫 <b>Подписка успешно аннулирована!</b>\n\n"
            f"👤 User ID: <code>{target_id}</code>",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer("❌ <b>Неверный формат!</b>\nОтправьте только Telegram ID.", parse_mode="HTML")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if ADMIN_IDS and call.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(AdminBroadcastState.waiting_for_message)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])
    await call.message.edit_text(
        "📢 <b>Массовая рассылка</b>\n\n"
        "Отправьте сообщение (текст, фото с текстом или видео) для рассылки.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(AdminBroadcastState.waiting_for_message)
async def process_admin_broadcast(message: Message, state: FSMContext, bot: Bot):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        return

    await state.clear()
    status_msg = await message.answer("⏳ <b>Рассылка запущенна...</b>", parse_mode="HTML")

    users = getattr(db, "get_all_users", lambda: [])()
    total_users = len(users)
    success, blocked, failed = 0, 0, 0

    for index, user_id in enumerate(users):
        try:
            await message.send_copy(chat_id=user_id)
            success += 1
        except Exception as e:
            err_str = str(e).lower()
            if "blocked" in err_str or "deactivated" in err_str or "chat not found" in err_str:
                blocked += 1
            else:
                failed += 1

        if index > 0 and index % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"⏳ <b>Рассылка в процессе... ({index}/{total_users})</b>\n\n"
                    f"✅ Успешно: <b>{success}</b>\n"
                    f"🚫 Заблокировали: <b>{blocked}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    await status_msg.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Успешно отправлено: <b>{success}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked}</b>\n"
        f"❌ Ошибок отправки: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_back")
async def admin_back_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    await admin_panel_btn(call.message, state, bot)


@router.callback_query(F.data == "admin_close")
async def admin_close_callback(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass


# --- ТАРИФЫ И ОПЛАТА ---
@router.callback_query(F.data == "buy_subscription")
async def buy_sub_menu(call: CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — $3.5", callback_data="plan_1day")],
        [InlineKeyboardButton(text="🔥 1 неделя — $8", callback_data="plan_1week")],
        [InlineKeyboardButton(text="🚀 1 месяц — $18", callback_data="plan_1month")],
        [InlineKeyboardButton(text="👨‍💻 Написать админу", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="check_tg_sub")]
    ])
    await call.message.edit_text("💳 <b>Выберите тариф подписки:</b>", reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("plan_"))
async def select_payment_method(call: CallbackQuery):
    await call.answer()
    plan = call.data.split("_")[1]
    plan_info = payments.PRICES.get(plan)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💎 CryptoBot (${plan_info['usd']})", callback_data=f"pay_cb_{plan}")],
        [InlineKeyboardButton(text=f"🚀 xRocket (${plan_info['usd']})", callback_data=f"pay_xr_{plan}")],
        [InlineKeyboardButton(text=f"⭐ Telegram Stars ({plan_info['stars']} ⭐)", callback_data=f"pay_stars_{plan}")],
        [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="buy_subscription")]
    ])

    await call.message.edit_text(
        f"💳 <b>Тариф:</b> {plan_info['title']}\n\nВыберите способ оплаты:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pay_"))
async def process_payment(call: CallbackQuery, bot: Bot):
    await call.answer("Генерация счета...")
    _, method, plan = call.data.split("_")
    user_id = call.from_user.id
    plan_info = payments.PRICES[plan]

    if method == "stars":
        invoice_link = await payments.create_stars_invoice(bot, user_id, plan)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Оплатить {plan_info['stars']} Stars", url=invoice_link)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"plan_{plan}")]
        ])
        return await call.message.edit_text(
            f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
            f"⏱ <b>Тариф:</b> {plan_info['title']}\n"
            f"💰 <b>К оплате:</b> {plan_info['stars']} Stars",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    if method == "cb":
        pay_url, invoice_id = await payments.create_cryptobot_invoice(user_id, plan)
        gate_name = "CryptoBot"
        check_prefix = "chk_cb"
    else:
        pay_url, invoice_id = await payments.create_xrocket_invoice(user_id, plan)
        gate_name = "xRocket"
        check_prefix = "chk_xr"

    if not pay_url:
        return await call.message.edit_text(
            "❌ <b>Ошибка выписки счета!</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=f"plan_{plan}")]]),
            parse_mode="HTML"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Оплатить счет", url=pay_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"{check_prefix}_{invoice_id}_{plan}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"plan_{plan}")]
    ])

    await call.message.edit_text(
        f"💳 <b>Счет на оплату ({gate_name})</b>\n\n"
        f"⏱ <b>Тариф:</b> {plan_info['title']}\n"
        f"💰 <b>Сумма:</b> ${plan_info['usd']}\n\n"
        f"1. Нажмите <b>«Оплатить счет»</b>.\n"
        f"2. После оплаты нажмите <b>«Проверить оплату»</b>.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("chk_"))
async def check_payment_status(call: CallbackQuery):
    _, method, invoice_id, plan = call.data.split("_")
    user_id = call.from_user.id
    days = payments.PRICES[plan]["days"]

    is_paid = await payments.check_cryptobot_invoice(
        invoice_id) if method == "cb" else await payments.check_xrocket_invoice(invoice_id)

    if is_paid:
        new_end = db.set_subscription(user_id, days)
        await call.answer("🎉 Оплата прошла успешно!", show_alert=True)
        await call.message.edit_text(f"🎉 <b>Подписка успешно активирована!</b>\n\n🟢 <b>Действует до:</b> {new_end}",
                                     parse_mode="HTML")
    else:
        await call.answer("❌ Счет еще не оплачен!", show_alert=True)


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    _, plan = payload.split("_")
    days = payments.PRICES[plan]["days"]
    new_end = db.set_subscription(message.from_user.id, days)
    await message.answer(f"🎉 <b>Оплата Stars прошла успешно!</b>\n\n🟢 <b>Подписка активирована до:</b> {new_end}",
                         parse_mode="HTML")


@router.callback_query(F.data == "check_tg_sub")
async def check_sub_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await is_subscribed(bot, user_id):
        await call.answer("✅ Подписка подтверждена!", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
        await send_welcome_menu(
            message=call.message,
            user_id=user_id,
            first_name=call.from_user.first_name if hasattr(call.from_user, 'first_name') else "User",
            username=call.from_user.username,
            bot=bot
        )
    else:
        await call.answer("❌ Вы всё ещё не подписаны на канал!", show_alert=True)