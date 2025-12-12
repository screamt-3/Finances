import os
from flask import Flask, request, abort
import telegram
from telegram.ext import Application # We'll reuse the existing application
from config import TELEGRAM_API_TOKEN, RENDER_EXTERNAL_URL

# --- CONFIGURATION (PLACEHOLDERS) ---
# Ensure these environment variables are set on Render
BOT_TOKEN = TELEGRAM_API_TOKEN
RENDER_EXTERNAL_URL = RENDER_EXTERNAL_URL

# Initialize the Flask App
app = Flask(__name__)

# --- Load Your Bot Application ---
# Import your setup function (you might need to move your main bot setup into a function)
# from .your_bot_file import setup_application 
# application = setup_application() 

# For simplicity, assume you create and configure your Application object here:
application = Application.builder().token(BOT_TOKEN).build()
# Add your handlers (e.g., your ConversationHandler) to the application instance here:
# application.add_handler(your_bot_file.create_transactions)
# ...

@app.route('/')
def hello():
    # A simple health check route for Render
    return "Telegram Bot is running!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
    """Handle incoming Telegram updates sent to our endpoint."""
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), application.bot)
        
        # Process the update using your existing Application instance
        # Note: This requires the application to be running in fully async mode
        await application.process_update(update)
        
        return 'ok'
    
    # If not a POST request to the webhook URL
    abort(400)

async def set_telegram_webhook():
    """Sets the Telegram Webhook URL on startup."""
    if BOT_TOKEN and RENDER_EXTERNAL_URL:
        webhook_url = f'{RENDER_EXTERNAL_URL}/{BOT_TOKEN}'
        print(f"Setting webhook to: {webhook_url}")
        
        # Use the application's bot instance to set the webhook
        await application.bot.set_webhook(url=webhook_url)
        print("Webhook set successfully.")

# --- Render Deployment Entry Point ---
if __name__ == '__main__':
    import asyncio

    # 1. Set the webhook asynchronously when the server starts
    asyncio.run(set_telegram_webhook())
    
    # 2. Start the Flask server
    # We use gunicorn in the Render Start Command, but run with app.run() locally
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))