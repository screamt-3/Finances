import os
import re
from config import TELEGRAM_API_TOKEN

import asyncio
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
        type TEXT,
        amount REAL,
        category TEXT,
        date TEXT
    )
''')
conn.commit()

# Conversation states
CATEGORY_SELECTION, AMOUNT = range(2)
STAT_TYPE, YEARLY_STATS, MONTHLY_STATS, SELECT_PERIOD, DATA_DISPLAY = range(5)
RECORD_TYPE, SELECT_DATE, AMOUNT = range(3)


# Helper functions
def add_transaction(user_id, trans_type, amount, category):
    date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('INSERT INTO transactions (user_id, type, amount, category, date) VALUES (?, ?, ?, ?, ?)',
                  (user_id, trans_type, amount, category, date))
    conn.commit()

def get_balance(user_id):
    cursor.execute('SELECT SUM(CASE WHEN type="income" THEN amount ELSE -amount END) FROM transactions WHERE user_id=?', (user_id,))
    result = cursor.fetchone()[0] or 0
    return result

def expenses_category():
    buttons = []
    row = []
    for i, cat in enumerate(PRESET_CATEGORIES, 1):
        row.append(InlineKeyboardButton(cat.capitalize(), callback_data=f'cat:{cat}'))
        if i % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton('Custom category', callback_data='cat:custom')])
    return buttons

def months():
    buttons = []
    row = []
    for i, month in enumerate(range(1, 13), 1):
        month_name = datetime(1900, month, 1).strftime('%B')
        row.append(InlineKeyboardButton(month_name, callback_data=f'month:{month}'))
        if i % 3 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons

def years():
    current_year = datetime.now().year
    buttons = []
    row = []
    for year in range(current_year, current_year - 5, -1):
        row.append(InlineKeyboardButton(str(year), callback_data=f'year:{year}'))   
        buttons.append(row)
        row = []
    return buttons

def month_overall(query, month_data):
    month = int(month_data.split(':', 1)[1])
    user_id = query.from_user.id
    cursor.execute('''
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id=? AND strftime('%m', date)=?
        GROUP BY type
    ''', (user_id, f'{month:02}'))
    results = cursor.fetchall()
    income = sum(amount for t_type, amount in results if t_type == 'income')
    expense = sum(amount for t_type, amount in results if t_type == 'expense')
    logger.info(f"Monthly stats for user {user_id} for month {month}: Income={income}, Expense={expense}")
    return f'Statistics for {datetime(1900, month, 1).strftime("%B")}:\n  Income: ${income:.2f}\n  Expenses: ${expense:.2f}\n  Net: ${income - expense:.2f}'

def month_breakdown(query, month_data):
    month = int(month_data.split(':', 1)[1])
    user_id = query.from_user.id
    cursor.execute('''
        SELECT category, SUM(amount) FROM transactions
        WHERE user_id=? AND strftime('%m', date)=? AND type="expense"
        GROUP BY category
        ORDER BY SUM(amount) DESC
    ''', (user_id, f'{month:02}'))
    results = cursor.fetchall()
    breakdown = "Expense Breakdown:\n"
    for category, amount in results:
        breakdown += f'  {category}: ${amount:.2f}\n'
    logger.info(f"Monthly breakdown for user {user_id} for month {month}: {results}")
    return breakdown if results else "No expenses recorded for this month."

def year_overall(query, year_data):
    year = int(year_data.split(':', 1)[1])
    user_id = query.from_user.id
    cursor.execute('''
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id=? AND strftime('%Y', date)=?
        GROUP BY type
    ''', (user_id, str(year)))
    results = cursor.fetchall()
    income = sum(amount for t_type, amount in results if t_type == 'income')
    expense = sum(amount for t_type, amount in results if t_type == 'expense')
    logger.info(f"Yearly stats for user {user_id} for year {year}: Income={income}, Expense={expense}")
    return f'Statistics for {year}:\n  Income: ${income:.2f}\n  Expenses: ${expense:.2f}\n  Net: ${income - expense:.2f}'

def year_breakdown(query, year_data):
    year = int(year_data.split(':', 1)[1])
    user_id = query.from_user.id
    cursor.execute('''
        SELECT category, SUM(amount) FROM transactions
        WHERE user_id=? AND strftime('%Y', date)=? AND type="expense"
        GROUP BY category
        ORDER BY SUM(amount) DESC
    ''', (user_id, str(year)))
    results = cursor.fetchall()
    breakdown = "Expense Breakdown:\n"
    for category, amount in results:
        breakdown += f'  {category}: ${amount:.2f}\n'
    logger.info(f"Yearly breakdown for user {user_id} for year {year}: {results}")
    return breakdown if results else "No expenses recorded for this year."

def balance_per_month(query, year_data):
    year = int(year_data.split(':', 1)[1])
    user_id = query.from_user.id
    
    cursor.execute('''
        SELECT strftime('%m', date) AS month, 
               SUM(CASE WHEN type="income" THEN amount ELSE -amount END) AS balance
        FROM transactions
        WHERE user_id=? AND strftime('%Y', date)=?
        GROUP BY month
        ORDER BY month
    ''', (user_id, str(year)))
    results = cursor.fetchall()
    
    if not results:
        return "No transactions recorded for this year."
    
    # Find max absolute value for scaling bars
    max_balance = max(abs(r[1]) for r in results)
    max_bar_length = 20  # adjust for visual fit
    
    balance_info = f"Balance per Month ({year}):\n\n"
    
    for month, balance in results:
        month_name = datetime(1900, int(month), 1).strftime('%b')  # e.g. Jan, Feb
        # Normalize bar length relative to max balance
        bar_length = int((abs(balance) / max_balance) * max_bar_length) if max_balance > 0 else 0
        bar_symbol = "█" if balance >= 0 else "░"
        bar = bar_symbol * bar_length
        
        # Format: Month | ██████     $123.45
        balance_info += f"{month_name:<4} | {bar:<{max_bar_length}} ${balance:>8.2f}\n"
    
    logger.info(f"Balance per month for user {user_id} for year {year}: {results}")
    return balance_info




PRESET_CATEGORIES = ['food', 'clothes', 'transport', 'coffee', 'salary', 'other']

# Predefined bot commands
def set_bot_commands(application):
    commands = [
        BotCommand("start", "Start a transaction"),
        BotCommand("stats", "Get statistics"),
        BotCommand("add", "Add a new record"),
        # Add more commands as needed
    ]
    return application.bot.set_my_commands(commands)

async def start_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start transaction command triggered by user {update.effective_user.id}, user_data: {context.user_data}")
    keyboard = [
        [InlineKeyboardButton('Add Expense', callback_data='start_expense'), InlineKeyboardButton('Add Income', callback_data='start_income')],
        [InlineKeyboardButton('Balance', callback_data='show_balance')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Use the buttons below to log transactions or view your balance.', reply_markup=reply_markup)
    return CATEGORY_SELECTION

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Stats command triggered by user {update.effective_user.id}, user_data: {context.user_data}")
    keyboard = [
        [InlineKeyboardButton('View Balance', callback_data='balance')],
        [InlineKeyboardButton('Monthly Stats', callback_data='monthly_stats'),
         InlineKeyboardButton('Yearly Stats', callback_data='yearly_stats')],
        [InlineKeyboardButton('Category Breakdown', callback_data='category_stats')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Select the statistics you want to view:', reply_markup=reply_markup)
    return STAT_TYPE


# Transaction creation handlers
async def start_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(text="Starting transaction...")
    data = query.data
    logger.info(f"Callback query received: {data} for user {query.from_user.id}, user_data: {context.user_data}")
    if data == 'start_expense':
        context.user_data['trans_type'] = 'expense'
        logger.info(f"Set trans_type: {context.user_data['trans_type']} for user {query.from_user.id}")
        await category_selection(update, context)
        return CATEGORY_SELECTION
    elif data == 'start_income':
        context.user_data['trans_type'] = 'income'
        await query.message.reply_text('Please enter the amount of income:')
        return AMOUNT
    elif data == 'show_balance':
        bal = get_balance(query.from_user.id)
        await query.message.reply_text(f'Current balance: ${bal:.2f}')
        return ConversationHandler.END
    return ConversationHandler.END

async def category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Category selection called for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Selecting category...")
    categories = expenses_category()
    await query.message.reply_text('Select a category for this transaction:', reply_markup=InlineKeyboardMarkup(categories))
    return CATEGORY_SELECTION

async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Amount handler called with message: {update.message.text} for user {update.effective_user.id}, state: {context.user_data.get('__CONVERSATION_STATE')}")
    logger.info(f"user_data: {context.user_data}")
    try:
        amount = float(update.message.text)
        user_id = update.effective_user.id
        trans_type = context.user_data.get('trans_type')
        category = context.user_data.get('category')
        if amount <= 0:
            await update.message.reply_text('Amount must be positive. Please enter a valid amount:')
            return AMOUNT
        if context.user_data['trans_type'] == 'income':
            add_transaction(user_id, trans_type, amount, "Salary")
            await update.message.reply_text(f'Added income: ${amount}')
            context.user_data.clear()
            return ConversationHandler.END
        if not category:
            logger.warning(f"Category missing for user {update.effective_user.id}")
            await update.message.reply_text('Category missing. Please start again with /start and pick a category.')
            return ConversationHandler.END
        add_transaction(user_id, trans_type, amount, category)
        await update.message.reply_text(f'Added {trans_type}: ${amount} under {category}')
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text('Invalid amount. Please enter a numeric amount (e.g., 12.50):')
        return AMOUNT

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"Category callback received: {data} for user {query.from_user.id}, user_data: {context.user_data}")
    if not data.startswith('cat:'):
        await query.message.reply_text('Unknown selection.')
        return ConversationHandler.END
    sel = data.split(':', 1)[1]
    if sel == 'custom':
        await query.message.reply_text('Please type the category name you want to use:')
        return CATEGORY_SELECTION
    context.user_data['category'] = sel
    await query.message.reply_text(f'Category selected: {sel}. Now please enter the amount:')
    logger.info(f"Transitioning to AMOUNT state with category: {sel} for user {query.from_user.id}")
    return AMOUNT

async def custom_category_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text.strip()
    if not cat:
        await update.message.reply_text('Category cannot be empty. Please enter a category:')
        return CATEGORY_SELECTION
    context.user_data['category'] = cat
    await update.message.reply_text(f'Category set to: {cat}. Now enter the amount:')
    return AMOUNT


# Stats commands
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Balance command triggered by user {update.effective_user.id}")
    bal = get_balance(update.effective_user.id)
    query = update.callback_query
    await query.answer("Fetching balance...")
    await query.message.reply_text(f'Current balance: ${bal:.2f}')
    return ConversationHandler.END

async def select_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Select year called for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Choose a year...")
    year_list = years()
    await query.message.reply_text('Select a year for statistics:', reply_markup=InlineKeyboardMarkup(year_list))
    # process yearly stat or choose next sub-period
    return SELECT_PERIOD if 'stats_type' in context.user_data and context.user_data['stats_type'] != 'yearly' else YEARLY_STATS

async def select_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Select month called for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Choose a month...")
    months_list = months()
    await query.message.reply_text('Select a month for statistics:', reply_markup=InlineKeyboardMarkup(months_list))
    # process monthly stat or choose next sub-period 
    return SELECT_PERIOD if 'stats_type' in context.user_data and context.user_data['stats_type'] != 'monthly' else MONTHLY_STATS

async def monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Monthly stats command triggered by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()
    context.user_data['stats_type'] = 'monthly'
    return await select_year(update, context)
    

async def month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Month callback received for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Month Selected")
    data = query.data
    if not data.startswith('month:'):
        await query.message.reply_text('Unknown selection.')
        return ConversationHandler.END
    # Calculate Overall stats for the month
    f_string_month_overall = month_overall(query, data)
    f_string_month_breakdown = month_breakdown(query, data)
    await query.message.reply_text(f"{f_string_month_overall}\n\n{f_string_month_breakdown}")
    return ConversationHandler.END

async def yearly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Yearly stats command triggered by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Choose a year...")
    context.user_data['stats_type'] = 'yearly'
    return await select_year(update, context)

async def year_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Year callback received for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Year Selected")
    data = query.data
    if not data.startswith('year:'):
        await query.message.reply_text('Unknown selection.')
        return ConversationHandler.END
    f_string_year_overall = year_overall(query, data)
    f_string_year_breakdown = year_breakdown(query, data)
    f_string_balance_per_month = balance_per_month(query, data)
    await query.message.reply_text(f"{f_string_year_overall}\n\n{f_string_balance_per_month}\n\n{f_string_year_breakdown}")
    return ConversationHandler.END

async def category_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Category stats command triggered by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer("Category stats not implemented yet.")
    await query.message.reply_text('Category statistics feature is under development.')
    return ConversationHandler.END


# Add records commands
async def add_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Add records command triggered by user {update.effective_user.id}, user_data: {context.user_data}")
    keyboard = [
        [InlineKeyboardButton('Add Expense', callback_data='start_expense'), InlineKeyboardButton('Add Income', callback_data='start_income')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Use the buttons below to add a new record.', reply_markup=reply_markup)
    return RECORD_TYPE

# Fallbacks and error handling
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Cancel command triggered by user {update.effective_user.id}, state: {context.user_data.get('__CONVERSATION_STATE')}, user_data: {context.user_data}")
    await update.message.reply_text('Operation cancelled.')
    context.user_data.clear()
    return ConversationHandler.END

async def debug_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received message outside conversation: {update.message.text} from user {update.effective_user.id}")
    await update.message.reply_text(f"Debug: Received message '{update.message.text}' but not processed by conversation.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.lower()
    known_commands = ['/start', '/cancel', '/balance']
    if command not in known_commands:
        logger.info(f"Unknown command received: {command} from user {update.effective_user.id}")
        await update.message.reply_text("Unknown command. Please send a number or use /start to begin.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}, user_data: {context.user_data}", exc_info=True)
    if update and update.message:
        await update.message.reply_text("An error occurred. Please try again with /start.")

async def debug_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Current conversation state for user {update.effective_user.id}: {context.user_data.get('__CONVERSATION_STATE')}, user_data: {context.user_data}")
    await update.message.reply_text(f"Please use /start to begin")
    return None

async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Raw update for user {update.effective_user.id}: {update.to_dict()}")
    return None




# Main function to start the bot
def main():
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    set_bot_commands(application)

    create_transactions = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_transaction, filters=filters.Regex('^/start$')),
        ],
        states={
            CATEGORY_SELECTION: [
                CallbackQueryHandler(start_transaction_callback, pattern='^(start_|show_balance)'),
                CallbackQueryHandler(category_callback, pattern='^cat:'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_category_text),
                MessageHandler(filters.ALL, debug_state),
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount),
                MessageHandler(filters.ALL, debug_state),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=filters.Regex('^/cancel$'))],
    )

    check_stats = ConversationHandler(
        entry_points=[
            CommandHandler('stats', stats, filters=filters.Regex('^/stats$')),
        ],
        states={
            STAT_TYPE: [
                CallbackQueryHandler(balance, pattern='^balance$'),
                CallbackQueryHandler(yearly_stats, pattern='^yearly_stats$'),
                CallbackQueryHandler(monthly_stats, pattern='^monthly_stats$'),
                MessageHandler(filters.ALL, debug_state),
            ],
            SELECT_PERIOD: [
                # 
                CallbackQueryHandler(select_month, pattern='^year:'),
                #CallbackQueryHandler(select_year, pattern='^year:'),
                MessageHandler(filters.ALL, debug_state),
            ],
            YEARLY_STATS: [
                CallbackQueryHandler(year_callback, pattern='^year:'),
                MessageHandler(filters.ALL, debug_state),
            ],
            MONTHLY_STATS: [
                CallbackQueryHandler(month_callback, pattern='^month:'),
                MessageHandler(filters.ALL, debug_state),
            ],
            
            DATA_DISPLAY: [
                MessageHandler(filters.ALL, debug_state),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=filters.Regex('^/cancel$'))],
    )

    create_records = ConversationHandler(
        entry_points=[
            CommandHandler('add', add_records, filters=filters.Regex('^/add$')),
        ],
        states={
            RECORD_TYPE: [
                CallbackQueryHandler(start_transaction_callback, pattern='^(start_|show_balance)'),
                CallbackQueryHandler(category_callback, pattern='^cat:'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_category_text),
                MessageHandler(filters.ALL, debug_state),
            ],
            SELECT_DATE: [
                # CallbackQueryHandler(select_date, pattern='^date:'),
                CallbackQueryHandler(select_month, pattern='^year:'),
                MessageHandler(filters.ALL, debug_state),
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount),
                MessageHandler(filters.ALL, debug_state),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=filters.Regex('^/cancel$'))],
    )
    #priority 1
    ## Create transaction handler
    application.add_handler(create_transactions, group=0)
    
    ## Stats command handler
    application.add_handler(check_stats, group=0)

    ## Add records handler
    application.add_handler(create_records, group=0)

    #priority 5
    # application.add_handler(MessageHandler(filters.ALL, debug_state), group=5)
    # application.add_handler(MessageHandler(filters.ALL, log_all_updates), group=0)
    # application.add_handler(CallbackQueryHandler(start_transaction_callback, pattern='^(start_|show_balance)'), group=0)
    # application.add_handler(CallbackQueryHandler(category_callback, pattern='^cat:'), group=0)
    # application.add_handler(CommandHandler('balance', balance, filters=filters.Regex('^/balance$')), group=0)
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, debug_message), group=3)
    # application.add_handler(MessageHandler(filters.COMMAND, unknown_command), group=4)
    # application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == '__main__':
    asyncio.run(main())