import logging
from datetime import datetime, timedelta
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_tasks = {}

async def start(update, context):
    text = """🤖 *Бот-напоминалка*

/today - задачи на сегодня
/week - задачи на неделю
/tasks - список задач
/report - статистика

Как добавить задачу:
напомни выпить воду каждый день в 8:00"""
    await update.message.reply_text(text, parse_mode="Markdown")


def parse_task(text):
    text = text.lower()
    
    match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not match:
        return None
    time_str = f"{match.group(1)}:{match.group(2)}"
    
    name = text.replace("напомни", "")
    if "каждый" in name:
        name = name.split("каждый")[0]
    elif " в " in name:
        name = name.split(" в ")[0]
    
    name = name.strip()
    if not name:
        name = "задача"
    
    return {"name": name, "time": time_str, "period": "daily"}


async def send_reminder_callback(context):
    """Отправляет напоминание"""
    data = context.job.data
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"done_{data['task_id']}")]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"🔔 Напоминание: {data['task_name']}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def schedule_reminder(chat_id, task_id, task, context):
    """Планирует напоминание"""
    now = datetime.now()
    hour, minute = map(int, task["time"].split(':'))
    
    remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if remind_time <= now:
        remind_time += timedelta(days=1)
    
    delay = (remind_time - now).total_seconds()
    
    context.application.job_queue.run_once(
        send_reminder_callback,
        delay,
        data={"chat_id": chat_id, "task_name": task["name"], "task_id": task_id}
    )
    print(f"✅ Запланировано: {task['name']} в {remind_time.strftime('%H:%M')}")


async def add_task(update, context):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" not in text:
        return False
    
    task = parse_task(text)
    if not task:
        await update.message.reply_text("Не понял формат. Пример: напомни выпить воду в 8:00")
        return True
    
    if chat_id not in user_tasks:
        user_tasks[chat_id] = {}
    
    task_id = f"{task['name']}_{task['time']}_{datetime.now().timestamp()}"
    user_tasks[chat_id][task_id] = task
    
    await update.message.reply_text(f"✅ Задача '{task['name']}' на {task['time']} сохранена!")
    
    await schedule_reminder(chat_id, task_id, task, context)
    return True


async def show_tasks(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("Нет задач")
        return
    
    tasks = list(user_tasks[chat_id].items())
    keyboard = []
    for i, (task_id, task) in enumerate(tasks, 1):
        keyboard.append([InlineKeyboardButton(f"🗑 {i}. {task['name']} - {task['time']}", callback_data=f"delete_{task_id}")])
    
    await update.message.reply_text("📋 Список задач:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("delete_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        task_name = user_tasks[chat_id][task_id]['name']
        del user_tasks[chat_id][task_id]
        await query.edit_message_text(f"✅ Задача '{task_name}' удалена!")


async def show_today(update, context):
    await update.message.reply_text("📅 Сегодня задач нет")


async def show_week(update, context):
    await update.message.reply_text("📆 На неделю задач нет")


async def show_report(update, context):
    total = len(user_tasks.get(update.effective_chat.id, {}))
    await update.message.reply_text(f"📊 Всего задач: {total}")


async def handle_message(update, context):
    await add_task(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", show_today))
    app.add_handler(CommandHandler("week", show_week))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("report", show_report))
    app.add_handler(CallbackQueryHandler(delete_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
