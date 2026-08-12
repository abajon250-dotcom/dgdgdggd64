import os
import asyncio
from dotenv import load_dotenv
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import db

router = Router()


# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_give_sub_user_id = State()
    waiting_give_sub_days = State()
    waiting_revoke_sub_user_id = State()
    waiting_broadcast_message = State()


def is_admin(user_id: int) -> bool:
    load_dotenv()
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        return False
    return str(user_id) == str(admin_id).strip()


@router.message(Command("admin"))
@router.message(F.text == "👨‍💻 Админ панель")
async def admin_panel_cmd(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return await message.answer("❌ <b>У вас нет прав администратора.</b>", parse_mode="HTML")

    await show_admin_menu(message)


@router.callback_query(F.data == "admin_menu")
async def admin_panel_callback(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    await show_admin_menu(call.message, is_edit=True)


async def show_admin_menu(message_obj: Message, is_edit: bool = False):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats_bot")],
        [InlineKeyboardButton(text="⚙️ Статистика VK аккаунтов", callback_data="admin_stats_vk")],
        [InlineKeyboardButton(text="📈 Статистика проливов", callback_data="admin_stats_proliv")],
        [
            InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_sub"),
            InlineKeyboardButton(text="🚫 Забрать подписку", callback_data="admin_revoke_sub")
        ],
        [InlineKeyboardButton(text="📢 Начать рассылку", callback_data="admin_start_broadcast")]
    ])
    text = "👑 <b>Админ-панель управления:</b>"
    if is_edit:
        await message_obj.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_obj.answer(text, reply_markup=keyboard, parse_mode="HTML")


# --- СТАТИСТИКА БОТА ---
@router.callback_query(F.data == "admin_stats_bot")
async def admin_stats_bot(call: CallbackQuery):
    await call.answer()
    total_users = db.get_total_users_count()
    active_subs = db.get_active_subs_count()
    await call.message.edit_text(
        f"📊 <b>Статистика пользователей:</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных подписок: <b>{active_subs}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


# --- СТАТИСТИКА VK АККАУНТОВ ---
@router.callback_query(F.data == "admin_stats_vk")
async def admin_stats_vk(call: CallbackQuery):
    await call.answer()
    stats = db.get_vk_accounts_stats()
    await call.message.edit_text(
        f"⚙️ <b>Статистика VK Аккаунтов:</b>\n\n"
        f"📁 Всего загружено аккаунтов: <b>{stats['total']}</b>\n"
        f"✅ Валидных (рабочих): <b>{stats['valid']}</b>\n"
        f"❌ Невалидных (заблокированных): <b>{stats['invalid']}</b>\n"
        f"📊 Процент валидности: <b>{stats['percent']}%</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


# --- СТАТИСТИКА ПРОЛИВОВ ---
@router.callback_query(F.data == "admin_stats_proliv")
async def admin_stats_proliv(call: CallbackQuery):
    await call.answer()
    stats = db.get_proliv_stats()
    await call.message.edit_text(
        f"📈 <b>Статистика проливов:</b>\n\n"
        f"🚀 Всего отправлено сообщений: <b>{stats['total']}</b>\n"
        f"✅ Успешно доставлено: <b>{stats['success']}</b>\n"
        f"❌ Ошибок при отправке: <b>{stats['errors']}</b>\n"
        f"📊 Успешность пролива: <b>{stats['percent']}%</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


# --- ВЫДАТЬ ПОДПИСКУ ---
@router.callback_query(F.data == "admin_give_sub")
async def start_give_sub(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminStates.waiting_give_sub_user_id)
    await call.message.edit_text(
        "🎁 <b>Выдача подписки</b>\n\n"
        "Введи Telegram ID пользователя:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_give_sub_user_id)
async def process_give_sub_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ ID должен состоять только из цифр. Попробуй еще раз:")

    await state.update_data(target_user_id=int(message.text))
    await state.set_state(AdminStates.waiting_give_sub_days)
    await message.answer("Введи количество дней подписки (например: 30):")


@router.message(AdminStates.waiting_give_sub_days)
async def process_give_sub_days(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Количество дней должно быть числом. Попробуй еще раз:")

    days = int(message.text)
    data = await state.get_data()
    target_user_id = data["target_user_id"]

    new_end = db.set_subscription(target_user_id, days)
    await state.clear()

    await message.answer(
        f"✅ Пользователю <code>{target_user_id}</code> успешно выдана подписка на <b>{days}</b> дней!\n"
        f"🟢 Новая дата окончания: <b>{new_end}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 В админку", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


# --- ЗАБРАТЬ ПОДПИСКУ ---
@router.callback_query(F.data == "admin_revoke_sub")
async def start_revoke_sub(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminStates.waiting_revoke_sub_user_id)
    await call.message.edit_text(
        "🚫 <b>Аннулирование подписки</b>\n\n"
        "Введи Telegram ID пользователя:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_revoke_sub_user_id)
async def process_revoke_sub_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ ID должен состоять только из цифр. Попробуй еще раз:")

    target_user_id = int(message.text)
    db.revoke_subscription(target_user_id)
    await state.clear()

    await message.answer(
        f"✅ Подписка пользователя <code>{target_user_id}</code> была успешно забранa!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 В админку", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


# --- МОДУЛЬ РАССЫЛКИ ---
@router.callback_query(F.data == "admin_start_broadcast")
async def start_broadcast_cmd(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminStates.waiting_broadcast_message)
    await call.message.edit_text(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправь текст или медиасообщение, которое получат все пользователи бота:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_broadcast_message)
async def process_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = db.get_all_user_ids()

    status_msg = await message.answer("🚀 Рассылка запущена...")

    success_count = 0
    error_count = 0

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            success_count += 1
            await asyncio.sleep(0.05)  # Задержка, чтобы не поймать лимиты Telegram API
        except Exception:
            error_count += 1

    await status_msg.edit_text(
        f"📊 <b>Рассылка завершена!</b>\n\n"
        f"✅ Доставлено: <b>{success_count}</b>\n"
        f"❌ Ошибок (заблокировали бота): <b>{error_count}</b>\n"
        f"👥 Всего обработано: <b>{len(user_ids)}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 В админку", callback_data="admin_menu")]]),
        parse_mode="HTML"
    )