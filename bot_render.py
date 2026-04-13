import logging
from datetime import datetime, timedelta
import re
import calendar
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Хранилище задач: {chat_id: {task_id: task_data}}
user_tasks = {}
# Хранилище выполненных задач для статистики
completed_tasks = {}

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


def parse_task(text):
    """Парсит текст задачи"""
    text = text.lower()
    
    # Ищем время
    time_match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not time_match:
        return None
    time_str = f"{time_match.group(1)}:{time_match.group(2)}"
    
    # Извлекаем название (всё между "напомни" и "в")
    name = text.replace("напомни", "")
    if "в " in name:
        name = name.split("в")[0]
    name = name.strip()
    if not name:
        name = "задача"
    
    # Определяем тип периодичности
    period = "daily"
    period_value = None
    end_date = None
    
    # Разовая задача на конкретную дату
    date_match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", text)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else datetime.now().year
        try:
            end_date = datetime(year, month, day)
            if end_date > datetime.now():
                period = "once"
        except:
            pass
    
    # Ежедневная задача
    if "каждый день" in text or "ежедневно" in text:
        period = "daily"
    
    # Задача по дням недели
    elif any(day in text for day in ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье", "пн", "вт", "ср", "чт", "пт", "сб", "вс"]):
        days = []
        for day_name, day_num in WEEKDAYS.items():
            if day_name in text:
                days.append(day_num)
        if days:
            period = "weekly"
            period_value = days
    
    return {"name": name, "time": time_str, "period": period, "period_value": period_value, "end_date": end_date, "created_at": datetime.now()}


def check_task_for_date(task, date):
    """Проверяет, должна ли задача выполняться в указанную дату"""
    period = task.get("period", "daily")
    
    if period == "once":
        end_date = task.get("end_date")
        if end_date:
            return date.date() == end_date.date()
        return False
    elif period == "daily":
        return True
    elif period == "weekly":
        period_value = task.get("period_value")
        if period_value:
            return date.weekday() in period_value
    return False


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет напоминание"""
    data = context.job.data
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"done_{data['task_id']}")]]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"🔔 Напоминание: {data['task_name']}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def schedule_task(chat_id, task_id, task, context):
    """Планирует напоминание"""
    now = datetime.now()
    hour, minute = map(int, task["time"].split(':'))
    
    # Для разовых задач
    if task.get("period") == "once":
        end_date = task.get("end_date")
        if end_date and end_date > now:
            remind_time = end_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if remind_time > now:
                delay = (remind_time - now).total_seconds()
                context.application.job_queue.run_once(
                    send_reminder, delay,
                    data={"chat_id": chat_id, "task_name": task["name"], "task_id": task_id}
                )
        return
    
    # Для периодических задач ищем ближайшую дату
    for days_ahead in range(30):
        next_date = now + timedelta(days=days_ahead)
        next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_date <= now:
            continue
        if check_task_for_date(task, next_date):
            delay = (next_date - now).total_seconds()
            context.application.job_queue.run_once(
                send_reminder, delay,
                data={"chat_id": chat_id, "task_name": task["name"], "task_id": task_id}
            )
            logging.info(f"Запланировано: {task['name']} на {next_date}")
            break


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🤖 *Бот-напоминалка*

*Команды:*
/today - задачи на сегодня
/tasks - список всех задач
/report - отчёт за текущий месяц
/delete [номер] - удалить задачу

*Как добавить задачу:*

📅 *Ежедневная:* `напомни выпить воду каждый день в 8:00`

📆 *По дням недели:* `напомни массаж каждый вторник и четверг в 18:00`

📌 *Разовая на дату:* `напомни встреча 15.04 в 14:00`

*Примеры:*
• напомни витамины каждый день в 10:00
• напомни йога по средам в 19:00
• напомни оплатить налоги 30.04 в 12:00"""
    await update.message.reply_text(text, parse_mode="Markdown")


async def add_task(update, context):
    """Добавляет задачу из текста"""
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" not in text:
        return False
    
    task = parse_task(text)
    if not task:
        await update.message.reply_text("❌ Не понял формат.\n\nПримеры:\n• напомни выпить воду каждый день в 8:00\n• напомни встреча 15.04 в 14:00")
        return True
    
    if chat_id not in user_tasks:
        user_tasks[chat_id] = {}
    
    task_id = f"{task['name']}_{task['time']}_{datetime.now().timestamp()}"
    user_tasks[chat_id][task_id] = task
    
    # Формируем сообщение о создании
    period_text = ""
    if task['period'] == 'daily':
        period_text = "ежедневно"
    elif task['period'] == 'weekly':
        days = [WEEKDAY_NAMES[d] for d in task['period_value']]
        period_text = f"по {', '.join(days)}"
    elif task['period'] == 'once':
        period_text = f"однократно {task['end_date'].strftime('%d.%m.%Y')}"
    
    await update.message.reply_text(
        f"✅ Задача *{task['name']}* добавлена!\n"
        f"⏰ Время: {task['time']}\n"
        f"📅 {period_text}",
        parse_mode="Markdown"
    )
    
    await schedule_task(chat_id, task_id, task, context)
    return True


async def show_tasks(update, context):
    """Показывает список всех задач"""
    chat_id = update.effective_chat.id
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 У вас нет задач.\n\nДобавьте: напомни выпить воду каждый день в 8:00")
        return
    
    tasks = list(user_tasks[chat_id].items())
    text = "📋 *Список задач:*\n\n"
    for i, (_, task) in enumerate(tasks, 1):
        period_str = ""
        if task['period'] == 'daily':
            period_str = "ежедневно"
        elif task['period'] == 'weekly':
            days = [WEEKDAY_NAMES[d] for d in task['period_value']]
            period_str = f"по {', '.join(days)}"
        elif task['period'] == 'once':
            period_str = f"однократно {task['end_date'].strftime('%d.%m.%Y')}"
        
        text += f"{i}. *{task['name']}* - {task['time']} ({period_str})\n"
    
    text += "\n🗑 /delete [номер] - удалить задачу"
    await update.message.reply_text(text, parse_mode="Markdown")


async def delete_task(update, context):
    """Удаляет задачу по номеру"""
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
            await update.message.reply_text("❌ Неверный номер. Используйте /tasks для просмотра")
    except ValueError:
        await update.message.reply_text("❌ Введите число: /delete 2")


async def show_today(update, context):
    """Показывает задачи на сегодня"""
    chat_id = update.effective_chat.id
    today = datetime.now().date()
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 Нет задач")
        return
    
    tasks = []
    for task in user_tasks[chat_id].values():
        if check_task_for_date(task, today):
            tasks.append(f"• {task['name']} - {task['time']}")
    
    if tasks:
        await update.message.reply_text(f"📅 *Задачи на сегодня ({today.strftime('%d.%m.%Y')}):*\n\n" + "\n".join(tasks), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"📭 На сегодня ({today.strftime('%d.%m.%Y')}) задач нет")


async def show_report(update, Update, context):
    """Показывает отчёт за текущий месяц"""
    chat_id = update.effective_chat.id
    today = datetime.now()
    
    # Получаем первый и последний день текущего месяца
    first_day = today.replace(day=1)
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    
    # Собираем статистику
    total_tasks = 0
    completed = 0
    
    if chat_id in user_tasks:
        for task in user_tasks[chat_id].values():
            total_tasks += 1
            # Проверяем, была ли задача выполнена (упрощённо)
            if task.get("completed", False):
                completed += 1
    
    percent = int(completed / total_tasks * 100) if total_tasks > 0 else 0
    
    report_text = f"""📊 *Отчёт за {today.strftime('%B %Y')}*

📋 Всего задач: {total_tasks}
✅ Выполнено: {completed}
❌ Пропущено: {total_tasks - completed}

📈 Продуктивность: {percent}%

---
Отчёт сформирован {today.strftime('%d.%m.%Y')}"""
    
    await update.message.reply_text(report_text, parse_mode="Markdown")


async def auto_monthly_report(context: ContextTypes.DEFAULT_TYPE):
    """Автоматический отчёт 1-го числа каждого месяца"""
    for chat_id in user_tasks.keys():
        today = datetime.now()
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        
        total_tasks = len(user_tasks.get(chat_id, {}))
        
        report_text = f"""📊 *Отчёт за {today.strftime('%B %Y')}*

📋 Всего задач: {total_tasks}

---
Это автоматический отчёт. Создавайте новые задачи и следите за продуктивностью!"""
        
        await context.bot.send_message(chat_id=chat_id, text=report_text, parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки 'Выполнить'"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("done_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        task = user_tasks[chat_id][task_id]
        task["completed"] = True
        
        # Сохраняем в статистику
        if chat_id not in completed_tasks:
            completed_tasks[chat_id] = []
        completed_tasks[chat_id].append({
            "task_name": task["name"],
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        
        await query.edit_message_text(f"✅ Отлично! *{task['name']}* выполнено!", parse_mode="Markdown")


async def handle_message(update, context):
    """Обрабатывает все сообщения"""
    await add_task(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", show_today))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("delete", delete_task))
    app.add_handler(CommandHandler("report", show_report))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Планируем ежемесячный отчёт на 1-е число в 9:00
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_monthly_report, 'cron', day=1, hour=9, args=[app])
    scheduler.start()
    
    print("🤖 Бот запущен на Render!")
    app.run_polling()


if __name__ == "__main__":
    main()
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
