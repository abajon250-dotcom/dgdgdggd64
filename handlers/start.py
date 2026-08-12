import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    PreCheckoutQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import db
from services.vk_service import check_vk_account, send_vk_message, get_vk_friends

router = Router()

CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]


# --- СОСТОЯНИЯ (FSM) ---
class VKUploadState(StatesGroup):
    waiting_for_accounts = State()


class BroadcastState(StatesGroup):
    waiting_for_message = State()


class AdminGiveSubState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_duration = State()


class AdminRevokeSubState(StatesGroup):
    waiting_for_user_id = State()


class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def make_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "[░░░░░░░░░░] 0%"
    filled = int(length * current / total)
    bar = "▓" * filled + "░" * (length - filled)
    percent = int(current / total * 100)
    return f"[{bar}] {percent}% ({current}/{total})"


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
        f"Добро пожаловать в <b>Zenith VK</b> — систему автоматизации и рассылок.\n"
        f"Используйте кнопки меню ниже:",
        reply_markup=reply_kb,
        parse_mode="HTML"
    )


# --- СТАРТ И ПРОВЕРКА ПОДПИСКИ ---
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


@router.callback_query(F.data == "check_tg_sub")
async def check_sub_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    if await is_subscribed(bot, call.from_user.id):
        await call.message.delete()
        await send_welcome_menu(
            message=call.message,
            user_id=call.from_user.id,
            first_name=call.from_user.first_name,
            username=call.from_user.username,
            bot=bot
        )
    else:
        await call.message.answer("❌ Вы все еще не подписались на канал!")


# --- ПРОФИЛЬ ---
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


# --- ПОДПИСКА И ОПЛАТА (Stars, CryptoBot, XRocket) ---
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
        [InlineKeyboardButton(text="⭐ Оплатить Telegram Stars", callback_data="pay_stars_menu")],
        [InlineKeyboardButton(text="🤖 CryptoBot", callback_data="pay_cryptobot")],
        [InlineKeyboardButton(text="🚀 XRocket", callback_data="pay_xrocket")]
    ])

    await message.answer(
        f"💳 <b>Управление подпиской</b>\n\n"
        f"⏳ Текущий статус: {sub_status}\n\n"
        f"Выберите удобный способ оплаты:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_stars_menu")
async def show_stars_tariffs(call: CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — 50 ⭐", callback_data="pay_1day")],
        [InlineKeyboardButton(text="🔥 1 неделя — 140 ⭐", callback_data="pay_1week")],
        [InlineKeyboardButton(text="🚀 1 месяц — 340 ⭐", callback_data="pay_1month")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_sub")]
    ])
    await call.message.edit_text("💳 <b>Выберите тарифный план (Telegram Stars):</b>", reply_markup=keyboard,
                                 parse_mode="HTML")


@router.callback_query(F.data == "back_to_sub")
async def back_to_subscription(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    await subscription_btn(call.message, state, bot)


@router.callback_query(F.data.in_({"pay_1day", "pay_1week", "pay_1month"}))
async def process_payment_tariff(call: CallbackQuery, bot: Bot):
    await call.answer()
    data = call.data

    if data == "pay_1day":
        title = "Подписка на 1 день"
        description = "Доступ к рассылке VK на 1 день"
        payload = "sub_1day"
        prices = [LabeledPrice(label="XTR", amount=50)]
    elif data == "pay_1week":
        title = "Подписка на 1 неделю"
        description = "Доступ к рассылке VK на 7 дней"
        payload = "sub_1week"
        prices = [LabeledPrice(label="XTR", amount=140)]
    else:
        title = "Подписка на 1 месяц"
        description = "Доступ к рассылке VK на 30 дней"
        payload = "sub_1month"
        prices = [LabeledPrice(label="XTR", amount=340)]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=title,
        description=description,
        payload=payload,
        currency="XTR",
        prices=prices
    )


@router.callback_query(F.data == "pay_cryptobot")
async def pay_cryptobot_handler(call: CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Оплатить через CryptoBot", url="https://t.me/CryptoBot")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_sub")]
    ])
    await call.message.edit_text(
        "🤖 <b>Оплата через CryptoBot</b>\n\n"
        "Нажмите кнопку ниже для перевода средств и получения подписки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_xrocket")
async def pay_xrocket_handler(call: CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Оплатить через XRocket", url="https://t.me/xrocket")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_sub")]
    ])
    await call.message.edit_text(
        "🚀 <b>Оплата через XRocket</b>\n\n"
        "Нажмите кнопку ниже для перехода к оплате:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload
    days = 1
    if "1week" in payload:
        days = 7
    elif "1month" in payload:
        days = 30

    db.set_subscription(message.from_user.id, days)
    await message.answer(f"✅ <b>Оплата прошла успешно!</b> Подписка продлена на <b>{days}</b> дней. 🎉",
                         parse_mode="HTML")


# --- МЕНЮ УПРАВЛЕНИЯ АККАУНТАМИ ---
@router.message(F.text.contains("Подключить аккаунты"))
async def connect_accs_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    if not db.is_sub_active(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="back_to_sub")]
        ])
        return await message.answer(
            f"❌ <b>Для подключения аккаунтов необходима активная подписка!</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    stats = db.get_vk_accounts_stats(user_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить аккаунты (.txt / текст)", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="📂 Мои аккаунты VK", callback_data="vk_accounts_list")],
        [InlineKeyboardButton(text="❌ Очистить все аккаунты", callback_data="vk_clear_all")]
    ])

    await message.answer(
        f"🔑 <b>Подключение VK аккаунтов</b>\n\n"
        f"📊 <b>Ваша статистика:</b>\n"
        f"• Всего аккаунтов: <b>{stats['total']}</b>\n"
        f"• Рабочих (валид): <b>{stats['valid']}</b>\n"
        f"• Ошибок (невалид): <b>{stats['invalid']}</b>\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "connect_accs_menu")
async def back_to_accs_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    await connect_accs_btn(call.message, state, bot)


# --- СПИСОК АККАУНТОВ ---
@router.callback_query(F.data == "vk_accounts_list")
async def show_vk_accounts_list(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id

    accounts = db.get_user_vk_accounts(user_id)
    if not accounts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Загрузить аккаунты", callback_data="vk_add_bulk")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
        ])
        return await call.message.edit_text("📂 <b>У вас пока нет загруженных аккаунтов.</b>", reply_markup=keyboard,
                                            parse_mode="HTML")

    text = f"📂 <b>Ваши аккаунты VK ({len(accounts)} шт.):</b>\n\n"

    for acc in accounts[:15]:
        full_name = acc.get('name', 'Неизвестно')
        friends = acc.get('friends', 0)
        is_valid = acc.get('is_valid', True)

        status = "🟢" if is_valid else "🔴"
        text += f"{status} <b>{full_name}</b>\n👥 Друзей: <code>{friends}</code>\n-------------------\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить еще", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="❌ Очистить все", callback_data="vk_clear_all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
    ])
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- МАССОВАЯ ЗАГРУЗКА АККАУНТОВ С ПРОГРЕСС-БАРОМ ---
@router.callback_query(F.data == "vk_add_bulk")
async def start_add_bulk(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(VKUploadState.waiting_for_accounts)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="connect_accs_menu")]
    ])

    await call.message.edit_text(
        "📥 <b>Загрузка VK аккаунтов</b>\n\n"
        "Отправьте сюда <b>.txt файл</b> с аккаунтами или отправьте их <b>текстом</b> (каждый с новой строки).\n\n"
        "📌 <i>Формат строк:</i>\n"
        "• <code>токен</code>\n"
        "• <code>логин:пароль:токен</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(VKUploadState.waiting_for_accounts, F.document | F.text)
async def process_accounts_input(message: Message, state: FSMContext, bot: Bot):
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

    raw_accounts = [line.strip() for line in lines if line.strip()]
    if not raw_accounts:
        return await message.answer("❌ Сообщение или файл не содержат строк.")

    total = len(raw_accounts)
    bar_str = make_progress_bar(0, total)
    status_msg = await message.answer(f"⏳ <b>Проверка аккаунтов через VK API...</b>\n{bar_str}", parse_mode="HTML")

    valid_added = 0
    invalid_count = 0
    report_lines = []

    for idx, raw_acc in enumerate(raw_accounts, 1):
        acc_info = await check_vk_account(raw_acc)

        if acc_info['valid']:
            valid_added += 1
            db.save_vk_account(
                user_id=message.from_user.id,
                token=acc_info['token'],
                name=acc_info['name'],
                friends=acc_info['friends']
            )
            report_lines.append(f"🟢 <b>{acc_info['name']}</b> | Друзей: {acc_info['friends']}")
        else:
            invalid_count += 1
            report_lines.append("🔴 Невалидный аккаунт")

        if idx % 3 == 0 or idx == total:
            current_bar = make_progress_bar(idx, total)
            try:
                await status_msg.edit_text(f"⏳ <b>Проверка аккаунтов...</b>\n{current_bar}", parse_mode="HTML")
            except Exception:
                pass

    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Список аккаунтов", callback_data="vk_accounts_list")]
    ])

    report_text = "\n".join(report_lines[:15])
    await status_msg.edit_text(
        f"✅ <b>Обработка завершена!</b>\n\n"
        f"🟢 Валидных добавлено: <b>{valid_added}</b>\n"
        f"🔴 Невалидных: <b>{invalid_count}</b>\n\n"
        f"<b>Результаты:</b>\n{report_text}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "vk_clear_all")
async def clear_all_accs(call: CallbackQuery):
    await call.answer()
    db.clear_user_vk_accounts(call.from_user.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить новые", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="connect_accs_menu")]
    ])
    await call.message.edit_text("🗑 <b>Все ваши VK аккаунты успешно удалены!</b>", reply_markup=keyboard,
                                 parse_mode="HTML")


# --- РАССЫЛКА ПО ДРУЗЬЯМ VK С ПРОГРЕСС-БАРОМ ---
@router.message(F.text.contains("Начать рассылку"))
async def start_broadcast_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if not await is_subscribed(bot, user_id):
        return await send_welcome_menu(message, user_id, message.from_user.first_name, message.from_user.username, bot)

    if not db.is_sub_active(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="back_to_sub")]
        ])
        return await message.answer("❌ <b>Для запуска рассылки необходима активная подписка!</b>",
                                    reply_markup=keyboard, parse_mode="HTML")

    accounts = db.get_user_vk_accounts(user_id)
    valid_accs = [a for a in accounts if a.get('is_valid', True)]

    if not valid_accs:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Подключить аккаунты", callback_data="vk_add_bulk")]
        ])
        return await message.answer("⚠️ <b>У вас нет рабочих VK аккаунтов!</b>\nСначала добавьте их.",
                                    reply_markup=keyboard, parse_mode="HTML")

    await state.set_state(BroadcastState.waiting_for_message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="connect_accs_menu")]
    ])

    await message.answer(
        f"🚀 <b>Запуск рассылки по друзьям VK</b>\n\n"
        f"✅ Готово аккаунтов к работе: <b>{len(valid_accs)}</b>\n\n"
        f"💬 Отправьте <b>текст сообщения</b> для рассылки друзьям со всех аккаунтов:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(BroadcastState.waiting_for_message, F.text)
async def process_broadcast_execution(message: Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()

    user_id = message.from_user.id
    accounts = db.get_user_vk_accounts(user_id)
    valid_accs = [a for a in accounts if a.get('is_valid', True)]

    status_msg = await message.answer("🚀 <b>Сбор списка друзей и подготовка рассылки...</b>", parse_mode="HTML")

    # Собираем всех получателей со всех аккаунтов
    tasks_pool = []
    for acc in valid_accs:
        token = acc['token']
        friend_ids = await get_vk_friends(token)
        if friend_ids:
            for fid in friend_ids:
                tasks_pool.append((token, fid))

    total_targets = len(tasks_pool)
    if total_targets == 0:
        return await status_msg.edit_text("❌ <b>Не найдено друзей ни на одном из подключенных аккаунтов!</b>",
                                          parse_mode="HTML")

    total_success = 0
    total_errors = 0

    for idx, (token, fid) in enumerate(tasks_pool, 1):
        res = await send_vk_message(token=token, target=str(fid), text=broadcast_text)
        if res.get("success"):
            total_success += 1
        else:
            total_errors += 1

        if idx % 3 == 0 or idx == total_targets:
            bar = make_progress_bar(idx, total_targets)
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Рассылка по друзьям идет...</b>\n"
                    f"{bar}\n"
                    f"📤 Успешно: {total_success} | 🔴 Ошибок: {total_errors}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await asyncio.sleep(1.2)

    await status_msg.edit_text(
        f"✅ <b>Рассылка по друзьям завершена!</b>\n\n"
        f"📤 Успешно отправлено: <b>{total_success}</b>\n"
        f"🔴 Ошибок отправки: <b>{total_errors}</b>",
        parse_mode="HTML"
    )


# --- АДМИН-ПАНЕЛЬ ---
@router.message(F.text.contains("Админ панель"))
async def admin_panel_btn(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return await message.answer("❌ <b>У вас нет доступа к админ-панели!</b>", parse_mode="HTML")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_bot_stats")],
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_sub")],
        [InlineKeyboardButton(text="🚫 Забрать подписку", callback_data="admin_revoke_sub")],
        [InlineKeyboardButton(text="📢 Рассылка по юзерам", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])
    await message.answer("👑 <b>Админ-панель управления Zenith VK:</b>", reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin_give_sub")
async def admin_give_sub_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminGiveSubState.waiting_for_user_id)
    await call.message.edit_text("👤 Введите <b>Telegram ID</b> пользователя для выдачи подписки:", parse_mode="HTML")


@router.message(AdminGiveSubState.waiting_for_user_id)
async def admin_give_sub_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введите корректный ID (число).")
    await state.update_data(target_user=int(message.text))
    await state.set_state(AdminGiveSubState.waiting_for_duration)
    await message.answer("⏳ Введите <b>количество дней</b> подписки:", parse_mode="HTML")


@router.message(AdminGiveSubState.waiting_for_duration)
async def admin_give_sub_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введите количество дней числом.")

    data = await state.get_data()
    target_user = data['target_user']
    days = int(message.text)

    db.set_subscription(target_user, days)

    await state.clear()
    await message.answer(f"✅ Подписка пользователю <code>{target_user}</code> выдана на {days} дней!",
                         parse_mode="HTML")


@router.callback_query(F.data == "admin_revoke_sub")
async def admin_revoke_sub_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminRevokeSubState.waiting_for_user_id)
    await call.message.edit_text("👤 Введите <b>Telegram ID</b> пользователя, у которого нужно забрать подписку:",
                                 parse_mode="HTML")


@router.message(AdminRevokeSubState.waiting_for_user_id)
async def admin_revoke_sub_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введите корректный ID.")

    db.revoke_subscription(int(message.text))
    await state.clear()
    await message.answer(f"🚫 Подписка у пользователя <code>{message.text}</code> успешно удалена.", parse_mode="HTML")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcastState.waiting_for_message)
    await call.message.edit_text("📢 Введите <b>текст рассылки</b> для всех пользователей бота:", parse_mode="HTML")


@router.message(AdminBroadcastState.waiting_for_message)
async def admin_broadcast_finish(message: Message, state: FSMContext, bot: Bot):
    text = message.text
    users = db.get_all_users()

    count = 0
    for user in users:
        try:
            await bot.send_message(user[0], text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Сообщение получили <b>{count}</b> пользователей.", parse_mode="HTML")


@router.callback_query(F.data == "admin_bot_stats")
async def admin_stats(call: CallbackQuery):
    users_count = db.get_users_count()
    await call.message.edit_text(f"📊 <b>Статистика бота:</b>\n\n👥 Всего пользователей: <b>{users_count}</b>",
                                 parse_mode="HTML")


@router.callback_query(F.data == "admin_close")
async def admin_close_callback(call: CallbackQuery):
    await call.answer()
    await call.message.delete()