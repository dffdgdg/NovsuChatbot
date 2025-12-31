"""
Точка входа для запуска Telegram-бота.
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from bot_handlers import TelegramBot
from config import BOT_TOKEN, ADMIN_IDS

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

bot_logic = TelegramBot()


async def start(update: Update, context):
    """Обработчик команды /start."""
    user_first_name = update.effective_user.first_name

    await update.message.reply_text(
        f"Привет, {user_first_name}! 👋\n\n"
        "Я умный помощник НовГУ.\n"
        "Выберите действие в меню или просто напишите свой вопрос!",
        reply_markup=bot_logic.main_keyboard()
    )


async def admin_command(update: Update, context):
    """Обработчик команды /admin."""
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🔐 Режим администратора",
            reply_markup=bot_logic.admin_keyboard()
        )
    else:
        await update.message.reply_text("⛔ Доступ запрещен")


def main():
    """Запуск бота."""
    if not BOT_TOKEN:
        logger.error("Не задан BOT_TOKEN!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    # Callback-обработчики
    app.add_handler(CallbackQueryHandler(
        bot_logic.handle_feedback,
        pattern=r"^fb_(yes|no):"
    ))
    app.add_handler(CallbackQueryHandler(
        bot_logic.handle_confirmation,
        pattern=r"^(confirm|other|noanswer|select):"
    ))
    app.add_handler(CallbackQueryHandler(
        bot_logic.handle_admin_reply,
        pattern=r"^reply:"
    ))

    # Текстовые сообщения
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        bot_logic.handle_message
    ))

    logger.info("🤖 Бот запущен!")
    logger.info(f"👑 Администраторы: {ADMIN_IDS}")

    app.run_polling()


if __name__ == "__main__":
    main()