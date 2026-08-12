import re
import random
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import get_user_vk_accounts, is_sub_active
from services.vk_service import send_vk_message

router = Router()

# Пул ваших купленных IPv4 прокси (в формате http://login:pass@ip:port)
PROXIES_POOL = [
    "http://user:pass@ip1:port",
    "http://user:pass@ip2:port",
    "http://user:pass@ip3:port"
]


class DirectBroadcastState(StatesGroup):
    select_account = State()
    input_text = State()
    input_delay = State()
    input_targets = State()


@router.message(F.text == "🚀 Начать пролив")
async def start_broadcast(message: Message, state: FSMContext):
    await state.clear()

    # Проверка подписки перед стартом
    if not await is_sub_active(message.from_user.id):
        return await message.answer(
            "🔒 **У вас нет активной подписки.**\nНажмите кнопку '💎 Подписка' в меню для активации.",
            parse_mode="Markdown"
        )

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
    await message.answer(
        "⏱ **Введите задержку (КД) в секундах:**\n"
        "• Одно число (например: `3`)\n"
        "• Или диапазон для рандома (например: `3-7`):",
        parse_mode="Markdown"
    )


@router.message(DirectBroadcastState.input_delay)
async def choose_targets(message: Message, state: FSMContext):
    delay_text = message.text.replace(" ", "")
    try:
        if "-" in delay_text:
            min_d, max_d = map(int, delay_text.split("-"))
            if min_d > max_d:
                min_d, max_d = max_d, min_d
        else:
            min_d = max_d = int(delay_text)

        await state.update_data(min_delay=min_d, max_delay=max_d)
        await state.set_state(DirectBroadcastState.input_targets)
        await message.answer(
            f"✅ Задержка установлена: от **{min_d}** до **{max_d}** сек.\n\n"
            "🎯 **Введите ID получателей** (каждый с новой строки или через пробел):",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ **Ошибка!** Введите целое число (например: `3`) или диапазон (например: `3-7`).")


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
    total = len(raw_ids)
    min_d = data['min_delay']
    max_d = data['max_delay']

    # Создаем сообщение прогресс-бара
    status_msg = await message.answer(
        f"⏳ **Запуск рассылки через аккаунт {acc['full_name']}...**\n"
        f"📊 Прогресс: 0 / {total} (0%)",
        parse_mode="Markdown"
    )

    success, fail = 0, 0
    log_lines = []
    max_log_lines = 5  # Количество последних строк лога

    for index, uid in enumerate(raw_ids, start=1):
        # Выбираем случайный прокси из пула
        active_proxy = random.choice(PROXIES_POOL)

        # Генерируем рандомную задержку в заданном диапазоне
        sleep_time = random.randint(min_d, max_d)

        try:
            res = await send_vk_message(
                token=acc['token'],
                user_id=int(uid),
                text=data['text'],
                proxy=active_proxy
            )
            if res:
                success += 1
                status_icon = "✅ Успешно"
            else:
                fail += 1
                status_icon = "❌ Ошибка"
        except Exception:
            fail += 1
            status_icon = "❌ Ошибка"

        log_line = f"• ID `{uid}` — {status_icon}"
        log_lines.append(log_line)

        if len(log_lines) > max_log_lines:
            log_lines.pop(0)

        percent = int((index / total) * 100)

        progress_text = (
                f"⏳ **Рассылка активна ({acc['full_name']})**\n\n"
                f"📊 **Прогресс:** {index} из {total} ({percent}%)\n"
                f"🟢 Успешно: `{success}` | 🔴 Ошибок: `{fail}`\n\n"
                f"**Последние действия:**\n" + "\n".join(log_lines)
        )

        try:
            await status_msg.edit_text(progress_text, parse_mode="Markdown")
        except Exception:
            pass  # Защита от Flood Wait

        await asyncio.sleep(sleep_time)

    # Итоги
    await status_msg.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"📊 Всего обработано: `{total}`\n"
        f"🟢 Успешно отправлено: `{success}`\n"
        f"🔴 Ошибок: `{fail}`",
        parse_mode="Markdown"
    )