import logging
from datetime import datetime
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLite setup
conn = sqlite3.connect('finances.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,  -- 'expense' or 'income'
        amount REAL,
        category TEXT,
        date TEXT
    )
''')
conn.commit()

# Conversation states
AMOUNT, CATEGORY = range(2)

# Helper function to add a transaction to SQLite
def add_transaction(user_id, trans_type, amount, category):
    date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('INSERT INTO transactions (user_id, type, amount, category, date) VALUES (?, ?, ?, ?, ?)',
                  (user_id, trans_type, amount, category, date))
    conn.commit()

# Helper function to get balance
def get_balance(user_id):
    cursor.execute('SELECT SUM(CASE WHEN type="income" THEN amount ELSE -amount END) FROM transactions WHERE user_id=?', (user_id,))
    result = cursor.fetchone()[0] or 0
    return result

# Helper function to get stats for today/month
def get_stats(user_id, period='day'):
    if period == 'day':
        date_filter = datetime.now().strftime('%Y-%m-%d')
        query = 'SELECT category, SUM(amount) FROM transactions WHERE user_id=? AND date=? AND type="expense" GROUP BY category'
        cursor.execute(query, (user_id, date_filter))
    else:  # month
        date_filter = datetime.now().strftime('%Y-%m')
        query = 'SELECT category, SUM(amount) FROM transactions WHERE user_id=? AND date LIKE ? AND type="expense" GROUP BY category'
        cursor.execute(query, (user_id, f'{date_filter}%'))
    return cursor.fetchall()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['/add_expense', '/add_income'], ['/stats day', '/stats month'], ['/balance']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text('Welcome! Use /add_expense or /add_income to log transactions, /stats for summaries, /balance for total.', reply_markup=reply_markup)

# Start adding expense
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['trans_type'] = 'expense'
    await update.message.reply_text('Please enter the amount for the expense:')
    return AMOUNT

# Start adding income
async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['trans_type'] = 'income'
    await update.message.reply_text('Please enter the amount for the income:')
    print("Adding income")
    return AMOUNT

# Handle amount input
async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text('Amount must be positive. Please enter a valid amount:')
            return AMOUNT
        context.user_data['amount'] = amount
        await update.message.reply_text('Please enter the category (e.g., coffee, salary):')
        return CATEGORY
    except ValueError:
        await update.message.reply_text('Invalid amount. Please enter a number:')
        return AMOUNT

# Handle category input
async def category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip()
    if not category:
        await update.message.reply_text('Category cannot be empty. Please enter a category:')
        return CATEGORY
    trans_type = context.user_data['trans_type']
    amount = context.user_data['amount']
    user_id = update.effective_user.id
    add_transaction(user_id, trans_type, amount, category)
    await update.message.reply_text(f'Added {trans_type}: ${amount} on {category}')
    return ConversationHandler.END

# Cancel conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

# Stats command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = context.args[0] if context.args else 'day'
    stats_data = get_stats(update.effective_user.id, period)
    if not stats_data:
        await update.message.reply_text(f'No {period} expenses yet.')
        return
    message = f'{period.capitalize()} Expenses:\n'
    for cat, amt in stats_data:
        message += f'{cat}: ${amt:.2f}\n'
    await update.message.reply_text(message)

# Balance command
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(update.effective_user.id)
    await update.message.reply_text(f'Current balance: ${bal:.2f}')

def main():
    # Replace with your token
    application = Application.builder().token('8340428743:AAH0v6SLoVeWX-vykLS0jrp2W_0DXV4PJVQ').build()

    # Conversation handler for adding transactions
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('add_expense', add_expense),
            CommandHandler('add_income', add_income),
        ],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('balance', balance))

    application.run_polling()

if __name__ == '__main__':
    main()