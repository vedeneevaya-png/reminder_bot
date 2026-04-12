import logging
from datetime import datetime, timedelta
import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_tasks = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка!\n\nНапиши: напомни выпить витамины в 10:00")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" in text:
        match = re.search(r"(\d{1,2})[:.](\d{2})", text)
        if match:
            time_str = f"{match.group(1)}:{match.group(2)}"
            task_name = text.replace("напомни", "").replace(time_str, "").strip()
            if not task_name:
                task_name = "задача"
            
            if chat_id not in user_tasks:
                user_tasks[chat_id] = {}
            
            task_id = f"{task_name}_{time_str}"
            user_tasks[chat_id][task_id] = {"name": task_name, "time": time_str, "status": "pending"}
            
            await update.message.reply_text(f"✅ Задача '{task_name}' на {time_str} сохранена!")
            
            now = datetime.now()
            hour, minute = map(int, time_str.split(':'))
            remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if remind_time < now:
                remind_time += timedelta(days=1)
            
            delay = (remind_time - now).total_seconds()
            context.job_queue.run_once(send_reminder, delay, data={"chat_id": chat_id, "task_name": task_name, "task_id": task_id})
        else:
            await update.message.reply_text("Не понял время. Пример: 'напомни выпить витамины в 10:00'")
    else:
        await update.message.reply_text("Напиши 'напомни [что делать] в [время]'")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"done_{data['task_id']}")]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"🔔 Напоминание: {data['task_name']}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("done_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        user_tasks[chat_id][task_id]["status"] = "done"
        await query.edit_message_text(f"✅ Отлично! {user_tasks[chat_id][task_id]['name']} выполнено!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен на Render!")
    app.run_polling()

if __name__ == "__main__":
    main()
import logging
from datetime import datetime, timedelta
import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_tasks = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка!\n\nНапиши: напомни выпить витамины в 10:00")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" in text:
        match = re.search(r"(\d{1,2})[:.](\d{2})", text)
        if match:
            time_str = f"{match.group(1)}:{match.group(2)}"
            task_name = text.replace("напомни", "").replace(time_str, "").strip()
            if not task_name:
                task_name = "задача"
            
            if chat_id not in user_tasks:
                user_tasks[chat_id] = {}
            
            task_id = f"{task_name}_{time_str}"
            user_tasks[chat_id][task_id] = {"name": task_name, "time": time_str, "status": "pending"}
            
            await update.message.reply_text(f"✅ Задача '{task_name}' на {time_str} сохранена!")
            
            now = datetime.now()
            hour, minute = map(int, time_str.split(':'))
            remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if remind_time < now:
                remind_time += timedelta(days=1)
            
            delay = (remind_time - now).total_seconds()
            context.job_queue.run_once(send_reminder, delay, data={"chat_id": chat_id, "task_name": task_name, "task_id": task_id})
        else:
            await update.message.reply_text("Не понял время. Пример: 'напомни выпить витамины в 10:00'")
    else:
        await update.message.reply_text("Напиши 'напомни [что делать] в [время]'")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"done_{data['task_id']}")]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"🔔 Напоминание: {data['task_name']}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("done_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        user_tasks[chat_id][task_id]["status"] = "done"
        await query.edit_message_text(f"✅ Отлично! {user_tasks[chat_id][task_id]['name']} выполнено!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен на Render!")
    app.run_polling()

if __name__ == "__main__":
    main()
