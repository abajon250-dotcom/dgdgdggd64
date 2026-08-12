from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

router = Router()


class VKProlivStates(StatesGroup):
    waiting_for_tokens = State()


# Главное меню модуля VK / Пролива
@router.callback_query(F.data.in_({"vk_menu", "proliv_menu"}))
async def vk_main_menu(call: CallbackQuery):
    await call.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Загрузить/Чекнуть токены", callback_data="vk_upload_tokens")],
        [InlineKeyboardButton(text="🛠 Запустить пролив / рассылку", callback_data="vk_start_proliv")],
        [InlineKeyboardButton(text="📊 Статистика аккаунтов", callback_data="vk_stats")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

    await call.message.edit_text(
        "🤖 <b>Панель управления VK и проливом:</b>\n\n"
        "Выберите нужное действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Шаг запроса токенов
@router.callback_query(F.data == "vk_upload_tokens")
async def upload_tokens_prompt(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(VKProlivStates.waiting_for_tokens)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="vk_menu")]
    ])

    await call.message.edit_text(
        "📥 <b>Загрузка VK аккаунтов:</b>\n\n"
        "Отправьте список токенов (доступны форматы: <code>token</code> или <code>login:password</code> или <code>access_token</code>) каждый с новой строки.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Обработка полученных токенов и валидация через VK API
@router.message(VKProlivStates.waiting_for_tokens)
async def process_tokens(message: Message, state: FSMContext):
    raw_text = message.text.strip()
    lines = raw_text.split("\n")

    valid_count = 0
    invalid_count = 0

    status_msg = await message.answer("🔄 <b>Проверяем токены через VK API...</b>", parse_mode="HTML")

    async with aiohttp.ClientSession() as session:
        for line in lines:
            token = line.strip()
            if not token:
                continue

            # Простейший запрос к VK API для проверки валидности токена (method: account.getProfileInfo)
            url = f"https://api.vk.com/method/account.getProfileInfo?access_token={token}&v=5.131"
            try:
                async with session.get(url, timeout=5) as resp:
                    data = await resp.json()
                    if "response" in data:
                        valid_count += 1
                        # Здесь можно добавить сохранение валидного токена в БД
                    else:
                        invalid_count += 1
            except Exception:
                invalid_count += 1

    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Загрузить еще", callback_data="vk_upload_tokens")],
        [InlineKeyboardButton(text="🔙 В меню VK", callback_data="vk_menu")]
    ])

    await status_msg.edit_text(
        f"✅ <b>Проверка завершена!</b>\n\n"
        f"🟢 Рабочих аккаунтов: <b>{valid_count}</b>\n"
        f"🔴 Недействительных: <b>{invalid_count}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Запуск пролива
@router.callback_query(F.data == "vk_start_proliv")
async def start_proliv_action(call: CallbackQuery):
    await call.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]
    ])

    await call.message.edit_text(
        "🚀 <b>Настройка пролива:</b>\n\n"
        "Модуль рассылки/пролива готов к работе. Загрузите активные аккаунты перед запуском задачи.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Статистика аккаунтов
@router.callback_query(F.data == "vk_stats")
async def vk_stats_action(call: CallbackQuery):
    await call.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="vk_menu")]
    ])

    await call.message.edit_text(
        "📊 <b>Статистика VK аккаунтов:</b>\n\n"
        "Всего в базе: <b>0</b>\n"
        "Активных (online): <b>0</b>\n"
        "Улетевших в бан: <b>0</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )