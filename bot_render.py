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
    text = """🤖 *Бот-напоминалка*

*Команды:*
/today - задачи на сегодня
/week - задачи на неделю
/tasks - список задач (с кнопками удаления 🗑)
/report - отчёт за месяц

*Как добавить задачу:*

📅 *Ежедневная:* `напомни выпить воду каждый день в 8:00`

📆 *По дням недели:* `напомни массаж каждый вторник и четверг в 18:00`

📌 *Разовая на дату:* `напомни встреча 15.04 в 14:00`

*Примеры:*
• напомни витамины каждый день в 10:00
• напомни йога по средам в 19:00
• напомни оплатить налоги 30.04 в 12:00"""
    await update.message.reply_text(text, parse_mode="Markdown")


def parse_task(text):
    text = text.lower()
    
    # Ищем время
    match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not match:
        return None
    time_str = f"{match.group(1)}:{match.group(2)}"
    
    # Проверяем, есть ли в тексте дни недели
    days_found = []
    for day_name, day_num in WEEKDAYS.items():
        if day_name in text:
            days_found.append(day_num)
    
    # Если нашли дни недели — это еженедельная задача
    if days_found:
        period = "weekly"
        period_value = days_found
    else:
        period = "daily"
        period_value = "*"
    
    # Извлекаем название задачи
    name = text.replace("напомни", "")
    name = name.replace(time_str, "")
    
    # Убираем дни недели из названия
    for day_name in WEEKDAYS.keys():
        name = name.replace(day_name, "")
    name = name.replace(",", "")
    name = name.replace("и", "")
    
    # Убираем фразы с периодичностью
    for phrase in ["каждый день", "ежедневно", "каждый"]:
        name = name.replace(phrase, "")
    
    # Убираем слово "в" перед временем
    if " в " in name:
        name = name.split(" в ")[0]
    elif " в" in name:
        name = name.split(" в")[0]
    
    name = name.strip()
    if not name:
        name = "задача"
    
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
    
    task_id = f"{task['name']}_{task['time']}_{datetime.now().timestamp()}"
    user_tasks[chat_id][task_id] = task
    
    await update.message.reply_text(f"✅ Задача '{task['name']}' на {task['time']} сохранена!")
    return True


async def show_tasks(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 У вас нет задач.\n\nДобавьте: напомни выпить воду каждый день в 8:00")
        return
    
    tasks = list(user_tasks[chat_id].items())
    keyboard = []
    for i, (task_id, task) in enumerate(tasks, 1):
        period_str = ""
        if task['period'] == 'daily':
            period_str = "ежедневно"
        elif task['period'] == 'weekly':
            days = [WEEKDAY_NAMES[d] for d in task['period_value']]
            period_str = f"по {', '.join(days)}"
        
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {i}. {task['name']} - {task['time']} ({period_str})",
                callback_data=f"delete_{task_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 *Список задач:*\n\nНажмите на задачу, чтобы удалить:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def delete_task_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("delete_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        task_name = user_tasks[chat_id][task_id]['name']
        del user_tasks[chat_id][task_id]
        await query.edit_message_text(f"✅ Задача *{task_name}* удалена!", parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ Задача не найдена")


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
        await update.message.reply_text(f"📅 Задачи на сегодня ({today.strftime('%d.%m.%Y')}):\n\n" + "\n".join(tasks))
    else:
        await update.message.reply_text(f"📭 На сегодня ({today.strftime('%d.%m.%Y')}) задач нет")


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
        result.append(f"*{weekday}* ({date.strftime('%d.%m.%Y')}):")
        if tasks_today:
            result.extend(tasks_today)
        else:
            result.append("  📭 нет задач")
        result.append("")
    
    await update.message.reply_text("\n".join(result), parse_mode="Markdown")


async def show_report(update, context):
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("Нет задач")
        return
    
    total = len(user_tasks[chat_id])
    await update.message.reply_text(f"📊 *Статистика*\n\nВсего задач: {total}", parse_mode="Markdown")


async def handle_message(update, context):
    await add_task(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", show_today))
    app.add_handler(CommandHandler("week", show_week))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("report", show_report))
    app.add_handler(CallbackQueryHandler(delete_task_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен на Render!")
    app.run_polling()

if __name__ == "__main__":
    main()
