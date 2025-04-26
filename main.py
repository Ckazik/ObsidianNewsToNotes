import os
import uuid
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импортируем токен из файла config.py
from config import BOT_TOKEN

# Путь к директории с заметками Obsidian
OBSIDIAN_DIR = "/var/www/webdav/obsidian"
# Поддиректория для вложений
ATTACHMENTS_DIR = os.path.join(OBSIDIAN_DIR, "attachments")
# Создаём поддиректорию, если её нет
if not os.path.exists(ATTACHMENTS_DIR):
    os.makedirs(ATTACHMENTS_DIR)

# Состояния для ConversationHandler
SELECT_ACTION, SELECT_NOTE, CREATE_NEW_NOTE = range(3)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Received /start command")
    await update.message.reply_text("Привет! Отправь мне новость (текст и/или изображение), и я добавлю её в заметки Obsidian. 😊")
    return SELECT_ACTION

# Обработка текстового сообщения или изображения
async def receive_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Received news message")
    # Инициализируем данные новости
    news_data = {"text": "", "images": []}
    
    # Если есть текст
    if update.message.text:
        news_data["text"] = update.message.text
        logger.info(f"Text received: {news_data['text']}")
    
    # Если есть изображения
    if update.message.photo:
        # Берем самое большое изображение (последнее в списке)
        photo = update.message.photo[-1]
        # Генерируем уникальное имя файла
        file_name = f"{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(ATTACHMENTS_DIR, file_name)
        
        # Скачиваем изображение
        logger.info(f"Downloading photo to {file_path}")
        photo_file = await photo.get_file()
        await photo_file.download_to_drive(file_path)
        
        # Добавляем ссылку на изображение в формате Markdown
        image_link = f"![Image {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}](attachments/{file_name})"
        news_data["images"].append(image_link)
        logger.info(f"Image link added: {image_link}")

    # Если нет ни текста, ни изображения
    if not news_data["text"] and not news_data["images"]:
        logger.warning("No text or image received")
        await update.message.reply_text("Пожалуйста, отправь текст или изображение!")
        return SELECT_ACTION

    # Сохраняем данные новости в контексте
    context.user_data['news'] = news_data

    # Создаём клавиатуру с опциями
    keyboard = [
        [InlineKeyboardButton("Добавить в существующую заметку", callback_data='existing')],
        [InlineKeyboardButton("Создать новую заметку", callback_data='new')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Что сделать с этой новостью?", reply_markup=reply_markup)
    return SELECT_ACTION

# Обработка выбора действия (новая заметка или существующая)
async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"Action selected: {query.data}")

    if query.data == 'new':
        await query.message.reply_text("Введите название новой заметки (без .md):")
        return CREATE_NEW_NOTE
    else:
        # Получаем список существующих заметок
        notes = [f for f in os.listdir(OBSIDIAN_DIR) if f.endswith('.md')]
        if not notes:
            logger.info("No existing notes found")
            await query.message.reply_text("Нет существующих заметок. Давай создадим новую!")
            await query.message.reply_text("Введите название новой заметки (без .md):")
            return CREATE_NEW_NOTE

        # Создаём клавиатуру с именами заметок
        keyboard = [[InlineKeyboardButton(note[:-3], callback_data=note)] for note in notes]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text("Выбери заметку для добавления:", reply_markup=reply_markup)
        return SELECT_NOTE

# Создание новой заметки
async def create_new_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note_name = update.message.text.strip() + ".md"
    news_data = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)
    logger.info(f"Creating new note: {note_name}")

    # Проверяем, существует ли заметка
    if os.path.exists(note_path):
        logger.warning(f"Note {note_name} already exists")
        await update.message.reply_text("Заметка с таким названием уже существует! Попробуй другое название:")
        return CREATE_NEW_NOTE

    # Собираем содержимое заметки
    content = f"# {note_name[:-3]}\n\n"
    if news_data["text"]:
        content += f"{news_data['text']}\n"
    if news_data["images"]:
        content += "\n".join(news_data["images"]) + "\n"

    # Создаём новую заметку
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"Note created at {note_path}")
    
    await update.message.reply_text(f"Новость добавлена в новую заметку: {note_name}")
    return ConversationHandler.END

# Добавление в существующую заметку
async def select_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    note_name = query.data
    news_data = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)
    logger.info(f"Appending to existing note: {note_name}")

    # Собираем содержимое для добавления
    content = ""
    if news_data["text"]:
        content += f"\n{news_data['text']}\n"
    if news_data["images"]:
        content += "\n".join(news_data["images"]) + "\n"

    # Добавляем новость в конец заметки
    with open(note_path, 'a', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"Content appended to {note_path}")
    
    await query.message.reply_text(f"Новость добавлена в заметку: {note_name}")
    return ConversationHandler.END

# Команда /cancel для отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Cancel command received")
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

def main() -> None:
    # Создаём приложение с увеличенным таймаутом
    application = Application.builder().token(BOT_TOKEN).read_timeout(30.0).write_timeout(30.0).connect_timeout(30.0).pool_timeout(30.0).build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, receive_news)
        ],
        states={
            SELECT_ACTION: [CallbackQueryHandler(select_action)],
            SELECT_NOTE: [CallbackQueryHandler(select_note)],
            CREATE_NEW_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_new_note)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)

    # Запуск бота
    logger.info("Starting bot polling")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()