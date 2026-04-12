import logging
from datetime import datetime, timedelta
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8793644570:AAFo_wp19_2DSLOYKnb8P7ti45Qfb3ryx2Q"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Хранилище задач: {chat_id: {task_id: task_data}}
user_tasks = {}

# Дни недели для распознавания
WEEKDAYS = {
    "пн": 0, "понедельник": 0,
    "вт": 1, "вторник": 1,
    "ср": 2, "среда": 2,
    "чт": 3, "четверг": 3,
    "пт": 4, "пятница": 4,
    "сб": 5, "суббота": 5,
    "вс": 6, "воскресенье": 6,
}

# Названия дней недели на русском
WEEKDAY_NAMES = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def get_instruction():
    """Возвращает текст инструкции для пользователя"""
    return """
🤖 *Бот-напоминалка - инструкция*

*📌 Основные команды:*
/today - задачи на сегодня
/week - задачи на неделю
/tasks - список всех задач
/report - статистика

*📝 Как добавить задачу:*

*Ежедневная задача:*
`напомни витамины каждый день в 10:00`

*По дням недели:*
`напомни танцы каждый вторник и четверг в 18:00`
`напомни йога по понедельникам и пятницам в 19:00`
`напомни массаж по средам в 15:00`

*По числам месяца:*
`напомни оплатить квартиру 15-го числа в 12:00`
`напомни сходить к стоматологу 1-го числа в 10:00`

*Простая задача (без повтора):*
`напомни купить хлеб в 18:00`

*💡 Советы:*
• Используйте слово "напомни" в начале сообщения
• Указывайте время в формате ЧЧ:ММ
• Для задач по дням недели пишите "каждый" или "по"

*🔔 Что делает бот:*
• Присылает напоминание в указанное время
• Ждёт нажатия кнопки "Выполнить"
• Показывает все задачи по командам

❓ *Вопросы и предложения:* напишите @vedeneevaya-png
    """


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и инструкция при команде /start"""
    await update.message.reply_text(
        get_instruction(),
        parse_mode="Markdown"
    )


def parse_task(text: str):
    """Парсит текст задачи: распознаёт дни недели, числа месяца, время"""
    text = text.lower()
    
    # Ищем время
    time_match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if not time_match:
        return None
    time_str = f"{time_match.group(1)}:{time_match.group(2)}"
    
    # Ищем название задачи (всё до "в" или до времени)
    task_name = text.split("в")[0].replace("напомни", "").strip()
    if not task_name:
        task_name = "задача"
    
    period = None
    period_value = None
    
    # Проверяем: "каждый день"
    if "каждый день" in text or "ежедневно" in text:
        period = "daily"
        period_value = "*"
    
    # Проверяем: дни недели ("вторник и четверг", "пн, вт", "по понедельникам")
    elif "каждый" in text or "по" in text:
        days = []
        for day_name, day_num in WEEKDAYS.items():
            if day_name in text:
                days.append(day_num)
        if days:
            period = "weekly"
            period_value = days
    
    # Проверяем: число месяца ("15-го числа", "каждое 15 число")
    if not period:
        month_match = re.search(r"(\d{1,2})(?:-го)?\s*числа", text)
        if month_match:
            period = "monthly"
            period_value = int(month_match.group(1))
    
    # Если не распознали — ежедневно по умолчанию
    if not period:
        period = "daily"
        period_value = "*"
    
    return {
        "name": task_name,
        "time": time_str,
        "period": period,
        "period_value": period_value
    }


def check_task_for_date(task, date):
    """Проверяет, должна ли задача выполняться в указанную дату"""
    period = task.get("period", "daily")
    period_value = task.get("period_value")
    
    if period == "daily":
        return True
    elif period == "weekly":
        weekday = date.weekday()
        return weekday in period_value
    elif period == "monthly":
        return date.day == period_value
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
    """Планирует следующее напоминание для задачи"""
    now = datetime.now()
    hour, minute = map(int, task["time"].split(':'))
    
    # Ищем ближайшую дату выполнения
    for days_ahead in range(60):  # ищем в пределах 60 дней
        next_date = now + timedelta(days=days_ahead)
        next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_date < now:
            continue
        
        if check_task_for_date(task, next_date):
            delay = (next_date - now).total_seconds()
            context.application.job_queue.run_once(
                send_reminder,
                delay,
                data={"chat_id": chat_id, "task_name": task["name"], "task_id": task_id}
            )
            break


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает добавление задачи из текста"""
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    
    if "напомни" not in text:
        return False
    
    task_data = parse_task(text)
    if not task_data:
        await update.message.reply_text("❌ Не понял формат.\n\nПримеры:\n• напомни витамины каждый день в 10:00\n• напомни танцы каждый вторник и четверг в 18:00\n• напомни оплатить квартиру 15-го числа в 12:00")
        return True
    
    if chat_id not in user_tasks:
        user_tasks[chat_id] = {}
    
    task_id = f"{task_data['name']}_{task_data['time']}_{task_data['period']}_{task_data['period_value']}"
    user_tasks[chat_id][task_id] = task_data
    
    # Формируем понятное описание периода
    period_text = ""
    if task_data['period'] == 'daily':
        period_text = "ежедневно"
    elif task_data['period'] == 'weekly':
        period_text = f"по {', '.join(WEEKDAY_NAMES[d] for d in task_data['period_value'])}"
    elif task_data['period'] == 'monthly':
        period_text = f"{task_data['period_value']}-го числа каждого месяца"
    
    await update.message.reply_text(
        f"✅ Задача добавлена!\n\n"
        f"📌 *{task_data['name']}*\n"
        f"⏰ Время: {task_data['time']}\n"
        f"📅 Повтор: {period_text}\n\n"
        f"Я напомню вовремя!",
        parse_mode="Markdown"
    )
    
    # Планируем задачу
    await schedule_task(chat_id, task_id, task_data, context)
    return True


async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает задачи на сегодня"""
    chat_id = update.effective_chat.id
    today = datetime.now().date()
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 У вас нет задач. Добавьте первую: 'напомни витамины каждый день в 10:00'")
        return
    
    tasks_today = []
    for task_id, task in user_tasks[chat_id].items():
        if check_task_for_date(task, today):
            tasks_today.append(f"• {task['name']} - {task['time']}")
    
    if tasks_today:
        await update.message.reply_text(f"📋 *Задачи на сегодня ({today.strftime('%d.%m.%Y')}):*\n\n" + "\n".join(tasks_today), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"📭 На сегодня ({today.strftime('%d.%m.%Y')}) задач нет.\n\nДобавьте задачу: 'напомни витамины каждый день в 10:00'")


async def show_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает задачи на неделю"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 У вас нет задач. Добавьте первую: 'напомни витамины каждый день в 10:00'")
        return
    
    result = ["📅 *Расписание на неделю:*\n"]
    for i in range(7):
        date = datetime.now().date() + timedelta(days=i)
        tasks_today = []
        for task_id, task in user_tasks[chat_id].items():
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


async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех задач"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 У вас нет задач.")
        return
    
    tasks_list = ["📋 *Список всех задач:*\n"]
    for i, (task_id, task) in enumerate(user_tasks[chat_id].items(), 1):
        period_str = ""
        if task['period'] == 'daily':
            period_str = "ежедневно"
        elif task['period'] == 'weekly':
            period_str = f"по {', '.join(WEEKDAY_NAMES[d] for d in task['period_value'])}"
        elif task['period'] == 'monthly':
            period_str = f"{task['period_value']}-го числа"
        
        tasks_list.append(f"{i}. *{task['name']}* - {task['time']} ({period_str})")
    
    await update.message.reply_text("\n".join(tasks_list), parse_mode="Markdown")


async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_tasks or not user_tasks[chat_id]:
        await update.message.reply_text("📭 Нет задач.")
        return
    
    total = len(user_tasks[chat_id])
    await update.message.reply_text(f"📊 *Статистика*\n\nВсего задач: {total}\n\nИспользуйте /tasks для просмотра списка.", parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки 'Выполнить'"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    task_id = query.data.replace("done_", "")
    
    if chat_id in user_tasks and task_id in user_tasks[chat_id]:
        task_name = user_tasks[chat_id][task_id]['name']
        del user_tasks[chat_id][task_id]
        await query.edit_message_text(f"✅ Отлично! *{task_name}* выполнено!", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все сообщения"""
    if await add_task(update, context):
        return


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", show_today))
    app.add_handler(CommandHandler("week", show_week))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("report", show_report))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен на Render!")
    app.run_polling()


if __name__ == "__main__":
    main()import logging
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
