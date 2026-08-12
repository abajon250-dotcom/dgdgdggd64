from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text == "📊 Рассылка / Шаблоны")
async def mailing_menu(message: Message):
    await message.answer(
        "📊 **Раздел рассылки и шаблонов**\n\nНастройте шаблоны сообщений для автоматической отправки.",
        parse_mode="Markdown"
    )