import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import db
from services.vk_service import check_vk_account, send_vk_message, get_vk_friends

router = Router()

CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
active_broadcasts = {}


# --- СОСТОЯНИЯ (FSM) ---
class VKUploadState(StatesGroup):
    waiting_for_accounts = State()


class BroadcastState(StatesGroup):
    selecting_account = State()
    waiting_for_message = State()


class AdminSubState(StatesGroup):
    user_id = State()
    duration = State()


class AdminRevokeState(StatesGroup):
    user_id = State()


class AdminBroadcastState(StatesGroup):
    message = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def make_bar(current: int, total: int, length: int = 12) -> str:
    if total <= 0: return "[░░░░░░░░░░░░] 0%"
    filled = int(length * current / total)
    return f"[{'▓' * filled + '░' * (length - filled)}] {int(current / total * 100)}%"


async def check_sub(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True


async def show_main(message: Message, user_id: int, name: str, username: str, bot: Bot):
    db.add_or_update_user(user_id, username)
    if not await check_sub(bot, user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        return await message.answer("⚠️ **Подпишитесь на канал для использования бота!**", reply_markup=kb,
                                    parse_mode="Markdown")

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Начать рассылку")],
        [KeyboardButton(text="🔑 Подключить аккаунты"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="👨‍💻 Админ панель")]
    ], resize_keyboard=True)
    await message.answer(f"👋 **Привет, {name}!** Добро пожаловать в Zenith VK.", reply_markup=kb, parse_mode="Markdown")


# --- СТАРТ И ПОДПИСКА НА КАНАЛ ---
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await show_main(message, message.from_user.id, message.from_user.first_name, message.from_user.username, bot)


@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    if await check_sub(bot, call.from_user.id):
        await call.message.delete()
        await show_main(call.message, call.from_user.id, call.from_user.first_name, call.from_user.username, bot)
    else:
        await call.message.answer("❌ Вы еще не подписались на канал!")


# --- ПРОФИЛЬ ---
@router.message(F.text.contains("Профиль"))
async def profile(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    if not await check_sub(bot, uid): return await start_cmd(message, state, bot)

    end = db.get_sub_end_date(uid)
    status = f"🟢 Активна до: {end.strftime('%d.%m.%Y %H:%M')}" if db.is_sub_active(uid) and end else "🔴 Отсутствует"
    await message.answer(
        f"👤 **Профиль:**\n\n🆔 ID: `{uid}`\n👤 Username: @{message.from_user.username or 'отсутствует'}\n⏳ Подписка: {status}",
        parse_mode="Markdown")


# --- ПОДПИСКИ И ОПЛАТА ---
@router.message(F.text.contains("Подписка"))
async def sub_menu(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    if not await check_sub(bot, uid): return await start_cmd(message, state, bot)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 1 день — 50 ⭐", callback_data="pay_1d")],
        [InlineKeyboardButton(text="🔥 1 неделя — 140 ⭐", callback_data="pay_1w")],
        [InlineKeyboardButton(text="🚀 1 месяц — 340 ⭐", callback_data="pay_1m")],
        [InlineKeyboardButton(text="🤖 CryptoBot", url="https://t.me/CryptoBot")],
        [InlineKeyboardButton(text="🚀 XRocket", url="https://t.me/xrocket")]
    ])
    await message.answer("💳 **Выберите тарифный план:**", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.in_({"pay_1d", "pay_1w", "pay_1m"}))
async def pay_stars(call: CallbackQuery, bot: Bot):
    await call.answer()
    tariffs = {"pay_1d": (1, 50, "1 день"), "pay_1w": (7, 140, "1 неделя"), "pay_1m": (30, 340, "1 месяц")}
    days, amount, title = tariffs[call.data]
    await bot.send_invoice(call.from_user.id, title=f"Подписка ({title})", description=f"Доступ на {title}",
                           payload=f"sub_{days}", currency="XTR", prices=[LabeledPrice(label="XTR", amount=amount)])


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(query.id, ok=True)


@router.message(F.successful_payment)
async def success_pay(message: Message):
    days = 7 if "7" in message.successful_payment.invoice_payload else (
        30 if "30" in message.successful_payment.invoice_payload else 1)
    db.set_subscription(message.from_user.id, days)
    await message.answer(f"✅ Оплата прошла успешно! Подписка продлена на {days} дней. 🎉")


# --- УПРАВЛЕНИЕ АККАУНТАМИ ---
@router.message(F.text.contains("Подключить аккаунты"))
async def accounts_menu(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    if not await check_sub(bot, uid): return await start_cmd(message, state, bot)
    if not db.is_sub_active(uid):
        return await message.answer("❌ Для подключения аккаунтов необходима активная подписка!")

    stats = db.get_vk_accounts_stats(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Загрузить аккаунты", callback_data="vk_add")],
        [InlineKeyboardButton(text="📂 Мои аккаунты", callback_data="vk_list")],
        [InlineKeyboardButton(text="🔄 Проверить все", callback_data="vk_check")],
        [InlineKeyboardButton(text="❌ Очистить", callback_data="vk_clear")]
    ])
    await message.answer(
        f"🔑 **Управление VK аккаунтами:**\n\nВсего: <b>{stats['total']}</b> | Рабочих: <b>{stats['valid']}</b>",
        reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "vk_list")
async def vk_list(call: CallbackQuery):
    await call.answer()
    accs = db.get_user_vk_accounts(call.from_user.id)
    if not accs: return await call.message.edit_text("📂 У вас нет аккаунтов.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ Загрузить", callback_data="vk_add")]]))

    text = f"📂 **Ваши аккаунты ({len(accs)}):**\n\n"
    for a in accs[:15]:
        text += f"{'🟢' if a.get('is_valid', True) else '🔴'} **{a.get('name')}** | Друзей: `{a.get('friends')}`\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="acc_menu")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "vk_add")
async def vk_add(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(VKUploadState.waiting_for_accounts)
    await call.message.edit_text("📥 Отправьте `.txt` файл или текст с токенами (каждый с новой строки):",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="❌ Отмена", callback_data="acc_menu")]]))


@router.message(VKUploadState.waiting_for_accounts, F.document | F.text)
async def vk_process_upload(message: Message, state: FSMContext, bot: Bot):
    lines = []
    if message.document:
        if not message.document.file_name.endswith('.txt'): return await message.answer("❌ Нужен `.txt` файл.")
        f = await bot.get_file(message.document.file_id)
        lines = (await bot.download_file(f.file_path)).read().decode('utf-8', errors='ignore').splitlines()
    elif message.text:
        lines = message.text.splitlines()

    tokens = [l.strip().split(":")[-1] for l in lines if l.strip()]
    if not tokens: return await message.answer("❌ Список пуст.")

    status = await message.answer("⏳ Проверка аккаунтов через VK API...")
    valid, invalid = 0, 0
    for t in tokens:
        res = await check_vk_account(t)
        if res['valid']:
            valid += 1
            db.save_vk_account(message.from_user.id, t, res['name'], res['friends'], True)
        else:
            invalid += 1
    await state.clear()
    await status.edit_text(f"✅ Проверка завершена!\n🟢 Валид: {valid}\n🔴 Невалид: {invalid}",
                           reply_markup=InlineKeyboardMarkup(
                               inline_keyboard=[[InlineKeyboardButton(text="📂 К списку", callback_data="vk_list")]]))


@router.callback_query(F.data == "vk_clear")
async def vk_clear(call: CallbackQuery):
    db.clear_user_vk_accounts(call.from_user.id)
    await call.message.edit_text("🗑 Все аккаунты успешно удалены!", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="acc_menu")]]))


# --- РАССЫЛКА ПО ДРУЗЬЯМ ---
@router.message(F.text.contains("Начать рассылку"))
async def start_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    if not await check_sub(bot, uid) or not db.is_sub_active(uid):
        return await message.answer("❌ Для рассылки необходима активная подписка!")

    accs = [a for a in db.get_user_vk_accounts(uid) if a.get('is_valid', True)]
    if not accs: return await message.answer("❌ Нет рабочих аккаунтов!")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"🟢 {a['name']} ({a['friends']} др.)", callback_data=f"b_acc_{i}")]
                         for i, a in enumerate(accs)])
    await state.set_state(BroadcastState.selecting_account)
    await state.update_data(accs=accs)
    await message.answer("🚀 Выберите аккаунт для рассылки:", reply_markup=kb)


@router.callback_query(BroadcastState.selecting_account, F.data.startswith("b_acc_"))
async def select_acc(call: CallbackQuery, state: FSMContext):
    await call.answer()
    acc = (await state.get_data())['accs'][int(call.data.split("_")[2])]
    check = await check_vk_account(acc['token'])
    if not check['valid']: return await call.message.edit_text("❌ Токен недействителен!")

    await state.update_data(token=acc['token'], name=check['name'])
    await state.set_state(BroadcastState.waiting_for_message)
    await call.message.edit_text(f"🚀 Выбран: **{check['name']}**\n💬 Отправьте текст сообщения:", parse_mode="Markdown")


@router.message(BroadcastState.waiting_for_message, F.text)
async def exec_broadcast(message: Message, state: FSMContext):
    data = await state.get_data()
    token, name, uid = data.get('token'), data.get('name'), message.from_user.id
    await state.clear()

    active_broadcasts[uid] = True
    status = await message.answer(f"🚀 Сбор друзей для «{name}»...", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛑 Отмена", callback_data="cancel_br")]]))

    friends = await get_vk_friends(token)
    if not friends:
        active_broadcasts.pop(uid, None)
        return await status.edit_text("❌ У аккаунта не найдено друзей!")

    success, errors = 0, 0
    for idx, fid in enumerate(friends, 1):
        if not active_broadcasts.get(uid, True): break
        if (await send_vk_message(token, str(fid), message.text)).get("success"):
            success += 1
        else:
            errors += 1

        if idx % 2 == 0 or idx == len(friends):
            try:
                await status.edit_text(
                    f"🚀 Рассылка с «{name}»\n{make_bar(idx, len(friends))}\n✅ Успешно: {success} | ❌ Ошибок: {errors}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="🛑 Отмена", callback_data="cancel_br")]]))
            except Exception:
                pass
        await asyncio.sleep(1.2)

    active_broadcasts.pop(uid, None)
    await status.edit_text(f"✅ Рассылка завершена!\n\n📤 Успешно: {success}\n🔴 Ошибок: {errors}")


@router.callback_query(F.data == "cancel_br")
async def cancel_br(call: CallbackQuery):
    active_broadcasts[call.from_user.id] = False
    await call.answer("🛑 Отмена принята...", show_alert=True)


# --- АДМИН-ПАНЕЛЬ ---
@router.message(F.text.contains("Админ панель"))
async def admin_panel(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS: return await message.answer("❌ У вас нет доступа!")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="adm_give")],
        [InlineKeyboardButton(text="🚫 Забрать подписку", callback_data="adm_rev")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_bc")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm_close")]
    ])
    await message.answer("👑 **Админ-панель:**", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    await call.message.edit_text(f"📊 Статистика:\n👥 Всего пользователей: <b>{db.get_users_count()}</b>",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]]),
                                 parse_mode="HTML")


@router.callback_query(F.data == "adm_give")
async def adm_give(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSubState.user_id)
    await call.message.edit_text("👤 Введите Telegram ID пользователя:")


@router.message(AdminSubState.user_id)
async def adm_give_id(message: Message, state: FSMContext):
    await state.update_data(uid=int(message.text))
    await state.set_state(AdminSubState.duration)
    await message.answer("⏳ Введите количество дней подписки:")


@router.message(AdminSubState.duration)
async def adm_give_dur(message: Message, state: FSMContext):
    data = await state.get_data()
    db.set_subscription(data['uid'], int(message.text))
    await state.clear()
    await message.answer(f"✅ Подписка выдана пользователю `{data['uid']}` на {message.text} дней!")


@router.callback_query(F.data == "adm_rev")
async def adm_rev(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminRevokeState.user_id)
    await call.message.edit_text("👤 Введите Telegram ID для удаления подписки:")


@router.message(AdminRevokeState.user_id)
async def adm_rev_done(message: Message, state: FSMContext):
    db.revoke_subscription(int(message.text))
    await state.clear()
    await message.answer(f"🚫 Подписка удалена у пользователя `{message.text}`.")


@router.callback_query(F.data == "adm_bc")
async def adm_bc(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcastState.message)
    await call.message.edit_text("📢 Введите текст рассылки для всех пользователей:")


@router.message(AdminBroadcastState.message)
async def adm_bc_done(message: Message, state: FSMContext, bot: Bot):
    text, count = message.text, 0
    for u in db.get_all_users():
        try:
            await bot.send_message(u[0], text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Получили: <b>{count}</b> пользователей.", parse_mode="HTML")


@router.callback_query(F.data.in_({"adm_close", "admin_back"}))
async def adm_close(call: CallbackQuery):
    await call.message.delete()