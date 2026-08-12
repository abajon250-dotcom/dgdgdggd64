import asyncio
import aiohttp
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import db
from services.vk_service import check_vk_account, get_vk_friends, send_vk_message

router = Router()

VK_CLIENT_ID = "2274003"
VK_CLIENT_SECRET = "hHbZxrka2uZ6jB1inYsH"
active_broadcasts = {}


class VKProlivStates(StatesGroup):
    waiting_for_accounts = State()
    waiting_for_message = State()
    waiting_for_delay = State()


async def check_access(event, user_id: int) -> bool:
    if not db.is_sub_active(user_id):
        text = "❌ **Доступ ограничен!** Требуется подписка."
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Подписка", callback_data="sub_menu")]])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await event.answer(text, reply_markup=kb, parse_mode="Markdown")
        return False
    return True


@router.message(F.text.contains("VK Аккаунты"))
async def text_vk_menu(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id): return
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
        [InlineKeyboardButton(text="📥 Загрузить аккаунты (.txt / текст)", callback_data="vk_upload_accounts")],
        [InlineKeyboardButton(text=f"🚀 Начать рассылку ({acc_count} акк.)", callback_data="vk_start_proliv")],
        [InlineKeyboardButton(text="🗑 Очистить список", callback_data="vk_clear_accounts")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="vk_stats")]
    ])
    text = f"🤖 **Панель управления VK:**\n\n📦 Валидных аккаунтов: **{acc_count} шт.**"
    if is_edit:
        await message_obj.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message_obj.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "vk_clear_accounts")
async def clear_accounts_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Список очищен!", show_alert=True)
    await show_main_menu(call.message, state, is_edit=True)


@router.callback_query(F.data == "vk_upload_accounts")
async def upload_accounts_prompt(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id): return
    await call.answer()
    await state.set_state(VKProlivStates.waiting_for_accounts)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]])
    await call.message.edit_text("📥 Отправьте `.txt` файл или текст с токенами / логин:пароль:", reply_markup=kb,
                                 parse_mode="Markdown")


@router.message(VKProlivStates.waiting_for_accounts)
async def process_accounts_batch(message: Message, state: FSMContext, bot):
    if not await check_access(message, message.from_user.id): return
    lines = []
    if message.document:
        file = await bot.get_file(message.document.file_id)
        lines = (await bot.download_file(file.file_path)).decode("utf-8", errors="ignore").splitlines()
    elif message.text:
        lines = message.text.splitlines()

    lines = [l.strip() for l in lines if l.strip()]
    if not lines: return await message.answer("❌ Список пуст.")

    status_msg = await message.answer(f"⏳ Проверка {len(lines)} аккаунтов с детектом банов...")
    valid_accounts, invalid_count = [], 0

    async with aiohttp.ClientSession() as session:
        for line in lines:
            token = None
            try:
                if ":" in line and not line.startswith("vk1.a"):
                    login, pwd = line.split(":", 1)
                    async with session.get("https://oauth.vk.com/token", params={
                        "grant_type": "password", "client_id": VK_CLIENT_ID,
                        "client_secret": VK_CLIENT_SECRET, "username": login.strip(),
                        "password": pwd.strip(), "v": "5.131"
                    }, timeout=5) as r:
                        data = await r.json()
                        token = data.get("access_token")
                else:
                    token = line

                if token:
                    res = await check_vk_account(token)
                    if res["valid"]:
                        valid_accounts.append({"token": token, "name": res["name"], "friends": res["friends"]})
                    else:
                        invalid_count += 1
                else:
                    invalid_count += 1
            except Exception:
                invalid_count += 1

    data = await state.get_data()
    accs = data.get("valid_accounts", [])
    accs.extend(valid_accounts)
    await state.update_data(valid_accounts=accs)
    await state.set_state(VKProlivStates.waiting_for_message)

    await status_msg.edit_text(
        f"✅ Проверка завершена!\n🟢 Валидных: {len(valid_accounts)}\n🔴 Невалидных / Заблокированных: {invalid_count}\n\n💬 Отправьте текст сообщения:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]]), parse_mode="Markdown"
    )


@router.callback_query(F.data == "vk_start_proliv")
async def callback_start_proliv(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id): return
    await call.answer()
    data = await state.get_data()
    if not data.get("valid_accounts"):
        return await call.message.edit_text("❌ Нет доступных аккаунтов!", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]]))
    await state.set_state(VKProlivStates.waiting_for_message)
    await call.message.edit_text("💬 Отправьте текст сообщения:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]]), parse_mode="Markdown")


@router.message(VKProlivStates.waiting_for_message)
async def get_proliv_text(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id): return
    await state.update_data(proliv_text=message.text)
    await state.set_state(VKProlivStates.waiting_for_delay)
    await message.answer("⏱ Введите задержку (кд) в секундах:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]]), parse_mode="Markdown")


@router.message(VKProlivStates.waiting_for_delay)
async def execute_proliv(message: Message, state: FSMContext):
    if not await check_access(message, message.from_user.id): return
    try:
        delay = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("❌ Введите число:")

    data = await state.get_data()
    accounts = data.get("valid_accounts", [])
    text = data.get("proliv_text", "")
    uid = message.from_user.id
    await state.clear()

    active_broadcasts[uid] = True
    progress_msg = await message.answer("🚀 Подготовка к рассылке...")

    for acc in accounts:
        if not active_broadcasts.get(uid, True): break
        acc_name = acc["name"]
        token = acc["token"]
        friends = await get_vk_friends(token)
        total_friends = len(friends)

        if total_friends == 0: continue

        success, errors = 0, 0
        for idx, friend_id in enumerate(friends, 1):
            if not active_broadcasts.get(uid, True): break

            res = await send_vk_message(token, str(friend_id), text)
            if res.get("success", False):
                success += 1
            else:
                errors += 1

            status_text = (
                f"📤 **Рассылка с аккаунта «{acc_name}»**\n\n"
                f"👥 Всего: {total_friends}\n"
                f"✅ Отправлено: {success}\n"
                f"🔴 Ошибок: {errors}\n"
                f"📊 Прогресс: {round((idx / total_friends) * 100, 1)}%\n"
                f"🔄 ID `{friend_id}` — {'✅ Успешно' if res.get('success') else '❌ Ошибка'}"
            )
            try:
                await progress_msg.edit_text(status_text, reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🛑 Стоп", callback_data="cancel_br")]]),
                                             parse_mode="Markdown")
            except Exception:
                pass
            await asyncio.sleep(delay)

        # ВОЗВРАЩЕН ВАШ ТОЧНЫЙ ФОРМАТ ОКОНЧАНИЯ РАССЫЛКИ С АККАУНТА
        completion_text = (
            f"✅ Рассылка с аккаунта «{acc_name}» завершена!\n\n"
            f"📤 Успешно отправлено: {success}\n"
            f"🔴 Ошибок отправки: {errors}\n"
            f"📊 Обработано друзей: {total_friends} из {total_friends}"
        )
        await message.answer(completion_text, parse_mode="Markdown")

    active_broadcasts.pop(uid, None)
    await message.answer("🎉 **Все рассылки завершены!**", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню VK", callback_data="vk_menu")]]), parse_mode="Markdown")


@router.callback_query(F.data == "cancel_br")
async def cancel_br(call: CallbackQuery):
    active_broadcasts[call.from_user.id] = False
    await call.answer("🛑 Рассылка остановлена!", show_alert=True)


@router.callback_query(F.data == "vk_stats")
async def vk_stats_action(call: CallbackQuery, state: FSMContext):
    if not await check_access(call, call.from_user.id): return
    await call.answer()
    data = await state.get_data()
    acc_count = len(data.get("valid_accounts", []))
    sub_end = db.get_sub_end_date(call.from_user.id)
    sub_str = sub_end.strftime("%d.%m.%Y %H:%M") if sub_end else "Нет"
    await call.message.edit_text(
        f"📊 **Статистика:**\n\n⏳ Подписка до: **{sub_str}**\n📦 Валидных аккаунтов: **{acc_count}**",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]]), parse_mode="Markdown")