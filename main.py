import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler

from config import BOT_TOKEN

OBSIDIAN_DIR = "/var/www/webdav/obsidian/Ckaz"
SELECT_ACTION, SELECT_NOTE, CREATE_NEW_NOTE = range(3)


def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Привет! Отправь мне новость, и я добавлю её в заметки Obsidian. 😊")
    return SELECT_ACTION

def receive_news(update: Update, context: CallbackContext) -> int:

    context.user_data['news'] = update.message.text

    #keyboard with options
    keyboard = [
        [InlineKeyboardButton("Добавить в существующую заметку", callback_data='existing')],
        [InlineKeyboardButton("Создать новую заметку", callback_data='new')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("Что сделать с этой новостью?", reply_markup=reply_markup)
    return SELECT_ACTION

#new or alredy created note
def select_action(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'new':
        query.message.reply_text("Введите название новой заметки (без .md):")
        return CREATE_NEW_NOTE
    else:
        #list of created notes
        notes = [f for f in os.listdir(OBSIDIAN_DIR) if f.endswith('.md')]
        if not notes:
            query.message.reply_text("Нет существующих заметок. Давай создадим новую!")
            query.message.reply_text("Введите название новой заметки (без .md):")
            return CREATE_NEW_NOTE

        #keyboards with created notes
        keyboard = [[InlineKeyboardButton(note[:-3], callback_data=note)] for note in notes]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.message.reply_text("Выбери заметку для добавления:", reply_markup=reply_markup)
        return SELECT_NOTE

#creating new note
def create_new_note(update: Update, context: CallbackContext) -> int:
    note_name = update.message.text.strip() + ".md"
    news = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)

    #cheking if it's note already created
    if os.path.exists(note_path):
        update.message.reply_text("Заметка с таким названием уже существует! Попробуй другое название:")
        return CREATE_NEW_NOTE

    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(f"# {note_name[:-3]}\n\n{news}\n")
    
    update.message.reply_text(f"Новость добавлена в новую заметку: {note_name}")
    return ConversationHandler.END

#add news in note
def select_note(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    note_name = query.data
    news = context.user_data['news']
    note_path = os.path.join(OBSIDIAN_DIR, note_name)

    #adding in the end of note
    with open(note_path, 'a', encoding='utf-8') as f:
        f.write(f"\n{news}\n")
    
    query.message.reply_text(f"Новость добавлена в заметку: {note_name}")
    return ConversationHandler.END

#cpmmand for cancel
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

def main() -> None:
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    #ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(Filters.text & ~Filters.command, receive_news)
        ],
        states={
            SELECT_ACTION: [CallbackQueryHandler(select_action)],
            SELECT_NOTE: [CallbackQueryHandler(select_note)],
            CREATE_NEW_NOTE: [MessageHandler(Filters.text & ~Filters.command, create_new_note)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()