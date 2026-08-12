import re
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import get_user_vk_accounts, is_sub_active
from services.vk_service import send_vk_message

router = Router()


class DirectBroadcastState(StatesGroup):
    select_account = State()
    input_text = State()
    input_delay = State()
    input_targets = State()


@router.message(F.text == "🚀 Начать пролив")
async def start_broadcast(message: Message, state: FSMContext):
    await state.clear()

    if not await is_sub_active(message.from_user.id):
        return await message.answer("🔒 У вас нет активной подписки.")

    accounts = await get_user_vk_accounts(message.from_user.id)
    valid_accs = [a for a in accounts if a['is_valid']]

    if not valid_accs:
        return await message.answer("❌ Нет валидных аккаунтов. Добавьте их в меню '⚙️ VK Аккаунты'.")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {a['full_name']}", callback_data=f"br_acc_{a['id']}")] for a in valid_accs
    ])

    await state.set_state(DirectBroadcastState.select_account)
    await message.answer("🚀 **Выберите рабочий аккаунт для рассылки:**", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(DirectBroadcastState.select_account, F.data.startswith("br_acc_"))
async def choose_text(call: CallbackQuery, state: FSMContext):
    await state.update_data(acc_id=int(call.data.split("_")[2]))
    await state.set_state(DirectBroadcastState.input_text)
    await call.message.edit_text("✍️ **Введите текст сообщения для рассылки:**", parse_mode="Markdown")


@router.message(DirectBroadcastState.input_text)
async def choose_delay(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(DirectBroadcastState.input_delay)
    await message.answer("⏱ **Введите задержку в секундах на 1 сообщение** (например: `3`):", parse_mode="Markdown")


@router.message(DirectBroadcastState.input_delay)
async def choose_targets(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введите целое число (секунды)!")
    await state.update_data(delay=int(message.text))
    await state.set_state(DirectBroadcastState.input_targets)
    await message.answer("🎯 **Введите ID получателей** (каждый с новой строки или через пробел):",
                         parse_mode="Markdown")


@router.message(DirectBroadcastState.input_targets)
async def final_run(message: Message, state: FSMContext):
    raw_ids = re.findall(r'\d+', message.text)
    if not raw_ids:
        return await message.answer("❌ Не найдено ни одного числового ID.")

    data = await state.get_data()
    accounts = await get_user_vk_accounts(message.from_user.id)
    acc = next((a for a in accounts if a['id'] == data['acc_id']), None)

    if not acc:
        await state.clear()
        return await message.answer("❌ Ошибка: аккаунт не найден.")

    await state.clear()
    status_msg = await message.answer(f"⏳ Запуск рассылки через аккаунт **{acc['full_name']}**...",
                                      parse_mode="Markdown")

    success, fail = 0, 0
    for uid in raw_ids:
        if await send_vk_message(acc['token'], int(uid), data['text']):
            success += 1
        else:
            fail += 1
        await asyncio.sleep(data['delay'])

    await status_msg.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"🟢 Успешно отправлено: `{success}`\n"
        f"🔴 Ошибок: `{fail}`",
        parse_mode="Markdown"
    )