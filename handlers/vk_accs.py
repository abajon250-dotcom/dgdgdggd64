from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import db

router = Router()


class VKAccStates(StatesGroup):
    waiting_for_accounts = State()


# --- СПИСОК АККАУНТОВ ---
@router.callback_query(F.data == "vk_accounts_list")
async def show_vk_accounts(call: CallbackQuery):
    await call.answer()
    accounts = db.get_user_vk_accounts()

    if not accounts:
        return await call.message.edit_text(
            "📭 <b>Список аккаунтов VK пуст.</b>\n\n"
            "Нажмите «➕ Загрузить аккаунты (.txt)», чтобы добавить их.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Загрузить аккаунты", callback_data="vk_add_bulk")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="check_tg_sub")]
            ]),
            parse_mode="HTML"
        )

    text = f"📁 <b>Загружено аккаунтов:</b> {len(accounts)}\n\n"
    valid_count = sum(1 for a in accounts if a[2] == 1)
    invalid_count = len(accounts) - valid_count

    text += f"✅ Валидных: <b>{valid_count}</b>\n"
    text += f"❌ Невалидных: <b>{invalid_count}</b>\n\n"
    text += "<i>Первые 10 аккаунтов в базе:</i>\n"

    for acc in accounts[:10]:
        acc_id, acc_data, is_valid = acc
        status = "✅" if is_valid else "❌"
        # Скрываем часть данных аккаунта для безопасности
        short_data = acc_data[:20] + "..." if len(acc_data) > 20 else acc_data
        text += f"{status} ID: {acc_id} | <code>{short_data}</code>\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еще (.txt)", callback_data="vk_add_bulk")],
        [InlineKeyboardButton(text="❌ Очистить все аккаунты", callback_data="vk_clear_all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="check_tg_sub")]
    ])

    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- СТАРТ ЗАГРУЗКИ (ИЗ ФАЙЛА ТЕКСТОМ ИЛИ .TXT) ---
@router.callback_query(F.data == "vk_add_bulk")
async def start_add_bulk(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(VKAccStates.waiting_for_accounts)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="vk_accounts_list")]
    ])

    await call.message.edit_text(
        "📥 <b>Загрузка VK аккаунтов</b>\n\n"
        "Отправьте сюда <b>.txt файл</b> с аккаунтами или отправьте их <b>текстом в сообщении</b>.\n\n"
        "<b>Формат (по одному на строку):</b>\n"
        "• Токен: <code>vk1.a.xxxxxx...</code>\n"
        "• Логин:пароль: <code>+79991112233:password</code>\n"
        "• Логин:пароль:токен: <code>+79991112233:pass:vk1.a.xxx</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# --- ОБРАБОТКА ТЕКСТОВОГО СООБЩЕНИЯ С АККАУНТАМИ ---
@router.message(VKAccStates.waiting_for_accounts, F.text)
async def process_accounts_text(message: Message, state: FSMContext):
    await state.clear()
    raw_lines = message.text.strip().split("\n")
    accounts = [line.strip() for line in raw_lines if line.strip()]

    if not accounts:
        return await message.answer("❌ Сообщение не содержит аккаунтов. Попробуйте еще раз.")

    added, skipped = db.add_vk_accounts_bulk(accounts)

    await message.answer(
        f"✅ <b>Успешно обработано!</b>\n\n"
        f"📥 Добавлено аккаунтов: <b>{added}</b>\n"
        f"⚠️ Пропущено (дубликаты/пустые): <b>{skipped}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📂 Посмотреть аккаунты", callback_data="vk_accounts_list")]
        ]),
        parse_mode="HTML"
    )


# --- ОБРАБОТКА .TXT ФАЙЛА С АККАУНТАМИ ---
@router.message(VKAccStates.waiting_for_accounts, F.document)
async def process_accounts_file(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.endswith(".txt"):
        return await message.answer("❌ Пожалуйста, отправьте файл в формате <b>.txt</b>", parse_mode="HTML")

    await state.clear()

    # Скачивание файла
    file_info = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    try:
        content = downloaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        content = downloaded_file.read().decode("cp1251", errors="ignore")

    raw_lines = content.strip().split("\n")
    accounts = [line.strip() for line in raw_lines if line.strip()]

    if not accounts:
        return await message.answer("❌ Файл пуст.")

    added, skipped = db.add_vk_accounts_bulk(accounts)

    await message.answer(
        f"📂 <b>Файл «{message.document.file_name}» успешно обработан!</b>\n\n"
        f"📥 Добавлено аккаунтов: <b>{added}</b>\n"
        f"⚠️ Пропущено (дубликаты): <b>{skipped}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📂 Посмотреть аккаунты", callback_data="vk_accounts_list")]
        ]),
        parse_mode="HTML"
    )


# --- ОЧИСТКА ВСЕХ АККАУНТОВ ---
@router.callback_query(F.data == "vk_clear_all")
async def clear_all_accs(call: CallbackQuery):
    await call.answer()
    db.clear_all_vk_accounts()
    await call.message.edit_text(
        "🗑 <b>Все VK аккаунты успешно удалены из базы!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Загрузить новые", callback_data="vk_add_bulk")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="check_tg_sub")]
        ]),
        parse_mode="HTML"
    )