import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler
import uuid
from datetime import datetime

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
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Привет! Отправь мне новость (текст и/или изображение), и я добавлю её в заметки Obsidian. 😊")
    return SELECT_ACTION

# Обработка текстового сообщения (новости)
def receive_news(update: Update, context: CallbackContext) -> int:
    # Инициализируем данные новости
    news_data = {"text": "", "images": []}
    
    # Если есть текст
    if update.message.text:
        news_data["text"] = update.message.text
    
    # Если есть изображения
    if update.message.photo:
        # Берем самое большое изображение (последнее в списке)
        photo = update.message.photo[-1]
        # Генерируем уникальное имя файла
        file_name = f"{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(ATTACHMENTS_DIR, file_name)
        
        # Скачиваем изображение
        photo_file = context.bot.get_file(photo.file_id)
        photo_file.download(file_path)
        
        # Добавляем ссылку на изображение в формате Markdown
        news_data["images"].append(f"![Image {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}](attachments/{file_name})")

    # Если нет ни текста, ни изображения
    if not news_data["text"] and not news_data["images"]:
        update.message.reply_text("Пожалуйста, отправь текст или изображение!")
        return SELECT_ACTION

    # Сохраняем данные новости в контексте
    context.user_data['news'] = news_data

    # Создаём клавиатуру с опциями
    keyboard = [
        [InlineKeyboardButton("Добавить в существующую заметку", callback_data='existing')],
        [InlineKeyboardButton("Создать новую заметку", callback_data='new')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("Что сделать с этой новостью?", reply_markup=reply_markup)
    return SELECT_ACTION

# Обработка выбора действия (новая заметка или существующая)
def select_action(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'new':
        query.message.reply_text("Введите название новой заметки (без .md):")
        return CREATE_NEW_NOTE
    else:
        # Получаем список существующих заметок
        notes = [f for f in os.listdir(OBSIDIAN_DIR) if f.endswith('.md')]
        if not notes:
            query.message.reply_text("Нет существующих заметок. Давай создадим новую!")
            query.message.reply_text("Введите название новой заметки (без .md):")
            return CREATE_NEW_NOTE

        # Создаём клавиатуру с именами заметок
        keyboard = [[InlineKeyboardButton(note[:-3], callback_data=note)] for note in notes]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.message.reply_text("Выбери заметку для добавления:", reply_markup=reply_markup)
        return SELECT_NOTE

# Создание новой заметки
def create_new_note(update: Update, context: CallbackContext) -> int:
    note_name = update.message.text.strip() + ".md"
    news_data = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)

    # Проверяем, существует ли заметка
    if os.path.exists(note_path):
        update.message.reply_text("Заметка с таким названием уже существует! Попробуй другое название:")
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
    
    update.message.reply_text(f"Новость добавлена в новую заметку: {note_name}")
    return ConversationHandler.END

# Добавление в существующую заметку
def select_note(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    note_name = query.data
    news_data = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)

    # Собираем содержимое для добавления
    content = ""
    if news_data["text"]:
        content += f"\n{news_data['text']}\n"
    if news_data["images"]:
        content += "\n".join(news_data["images"]) + "\n"

    # Добавляем новость в конец заметки
    with open(note_path, 'a', encoding='utf-8') as f:
        f.write(content)
    
    query.message.reply_text(f"Новость добавлена в заметку: {note_name}")
    return ConversationHandler.END

# Команда /cancel для отмены
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

def main() -> None:
    # Используем токен из config.py
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Настройка ConversationHandler с явным per_message=True
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler((Filters.text | Filters.photo) & ~Filters.command, receive_news)
        ],
        states={
            SELECT_ACTION: [CallbackQueryHandler(select_action)],
            SELECT_NOTE: [CallbackQueryHandler(select_note)],
            CREATE_NEW_NOTE: [MessageHandler(Filters.text & ~Filters.command, create_new_note)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True
    )

    dp.add_handler(conv_handler)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()