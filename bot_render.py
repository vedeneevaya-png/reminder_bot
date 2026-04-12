import logging
from datetime import datetime, timedelta
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_tasks = {}

WEEKDAYS = {
    "пн": 0, "понедельник": 0,
    "вт": 1, "вторник": 1,
    "ср": 2, "среда": 2,
    "чт": 3, "четверг": 3,
    "пт": 4, "пятница": 4,
    "сб": 5, "суббота": 5,
    "вс": 6, "воскресенье": 6,
}

WEEKDAY_NAMES = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🤖 Бот-напоминалка

/today - задачи на сегодня
/week - задачи на неделю
/tasks - список задач
/delete [номер] - удалить задачу

Как добавить задачу:
напомни витамины каждый день в 10:00
напомни танцы каждый вторник и четверг в 18:00
напомни оплатить квартиру 15-го числа в 12:00"""
    await update.message.reply_text(text)


def parse_task(text):
    text = text.lower()
    match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not match:
        return None
    time_str = f"{match.group(1)}:{match.group(2)}"
    
    name = text.split("в")[0].replace("напомни", "").strip()
    if not name:
        name = "задача"
    
    period = "daily"
    period_value = "*"
    
    if "каждый день" in text:
        period = "daily"
    elif "вторник" in text or "четверг" in text or "понедельник" in text:
        days = []
        for day_name, day_num in WEEKDAYS.items():
            if day_name in text:
                days.append(day_num)
        if days:
            period = "weekly"
            period_value = days
    
    return {"name": name, "time": time_str, "period": period, "period_value": period_value}


def check_task_for_date(task, date):
    if task["period"] == "daily":
        return True
    elif task["period"] == "weekly":
        return date.weekday() in task["period_value"]
    return False


async def add_task(update, context):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" not in text:
        return False
    
    task = parse_task(text)
    if not task:
        await update.message.reply_text("Не понял формат. Пример: напомни витамины каждый день в 10:00")
        return True
    
    if chat_id not in user_tasks:
        user_tasks[chat_id] = {}
    
    task_id = f"{task['name']}_{task['time']}"
    user_tasks[chat_id][task_id] = task
    
    await update.message.reply_text(f"✅ Задача '{task['name']}' на {task['time']} сохранена!")
    return True


async def show_tasks(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("Нет задач")
        return
    
    tasks = list(user_tasks[chat_id].items())
    text = "📋 Список задач:\n"
    for i, (_, task) in enumerate(tasks, 1):
        text += f"{i}. {task['name']} - {task['time']}\n"
    await update.message.reply_text(text)


async def delete_task(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in user_tasks:
        await update.message.reply_text("Нет задач")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Используйте: /delete 1")
        return
    
    try:
        num = int(args[0]) - 1
        tasks = list(user_tasks[chat_id].items())
        if 0 <= num < len(tasks):
            task_id, task = tasks[num]
            del user_tasks[chat_id][task_id]
            await update.message.reply_text(f"✅ Задача '{task['name']}' удалена")
        else:
            await update.message.reply_text("Неверный номер")
    except ValueError:
        await update.message.reply_text("Введите число")


async def show_today(update, context):
    chat_id = update.effective_chat.id
    today = datetime.now().date()
    
    if chat_id not in user_tasks:
        await update.message.reply_text("Нет задач")
        return
    
    tasks = []
    for task in user_tasks[chat_id].values():
        if check_task_for_date(task, today):
            tasks.append(f"• {task['name']} - {task['time']}")
    
    if tasks:
        await update.message.reply_text(f"Задачи на сегодня:\n" + "\n".join(tasks))
    else:
        await update.message.reply_text("На сегодня задач нет")


async def show_week(update, context):
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("Нет задач")
        return
    
    result = ["📅 Расписание на неделю:\n"]
    for i in range(7):
        date = datetime.now().date() + timedelta(days=i)
        tasks_today = []
        for task in user_tasks[chat_id].values():
            if check_task_for_date(task, date):
                tasks_today.append(f"  • {task['name']} - {task['time']}")
        
        weekday = WEEKDAY_NAMES[date.weekday()]
        result.append(f"{weekday} ({date.strftime('%d.%m.%Y')}):")
        if tasks_today:
            result.extend(tasks_today)
        else:
            result.append("  нет задач")
        result.append("")
    
    await update.message.reply_text("\n".join(result))


async def show_report(update, context):
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("Нет задач")
        return
    
    total = len(user_tasks[chat_id])
    await update.message.reply_text(f"📊 Статистика\n\nВсего задач: {total}")


async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Выполнено!")


async def handle_message(update, context):
    await add_task(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", show_today))
    app.add_handler(CommandHandler("week", show_week))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("report", show_report))
    app.add_handler(CommandHandler("delete", delete_task))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен на Render!")
    app.run_polling()


if __name__ == "__main__":
    main()
