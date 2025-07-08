from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN, ADMIN_IDS
from db import init_db, get_user, increment_usage, reset_monthly_usage, update_user
from openai_utils import threadsify_text
from datetime import datetime
import sys
sys.path.append('threads-rag')
from threads-rag.index import get_rag_results
from telegram.constants import ChatAction

FREE_LIMIT = 5
PRO_LIMIT = 500

# Список доступных стилей
STYLES = [
    ("Мем", "мем"),
    ("Ирония", "ирония"),
    ("Цитата", "цитата"),
    ("Сарказм", "сарказм"),
    ("Инфо", "инфо"),
    ("ИИ", "ии"),
]

# user_id -> {'styles': [...], 'random': bool}
user_styles = {}

LOG_PATH = "logs.txt"

def log_interaction(user_id, prompt, selected_styles, response):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] user_id={user_id}\n")
        f.write(f"prompt: {prompt}\n")
        f.write(f"selected_styles: {selected_styles}\n")
        f.write(f"response: {response}\n")
        f.write("---\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        now_month = datetime.now().strftime("%Y-%m")
        update_user(user_id, last_reset=now_month)
        user = get_user(user_id)
    plan, used, last_reset = user
    if user_id in ADMIN_IDS:
        left = '∞'
    else:
        left = (PRO_LIMIT if plan == "pro" else FREE_LIMIT) - (used or 0)
    msg = (
        "👋 Привет! Я бот для создания Threads-каруселей.\n\n"
        "Просто отправь мне текст, и я преобразую его в формат Threads.\n\n"
        f"У вас осталось {left} генераций в этом месяце.\n"
        "Для получения Pro-подписки свяжитесь с администратором.\n"
        "Для связи @kromakhov"
    )
    await update.message.reply_text(msg)
    # Показываем кнопки выбора стиля
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"style_{value}") for text, value in STYLES[:3]],
        [InlineKeyboardButton(text, callback_data=f"style_{value}") for text, value in STYLES[3:]],
        [InlineKeyboardButton("🎲 Случайный стиль", callback_data="style_random"), InlineKeyboardButton("Готово", callback_data="style_done")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_msg = await update.message.reply_text("Выберите стили для поста (можно несколько):", reply_markup=reply_markup)
    context.user_data['menu_message_id'] = menu_msg.message_id

async def style_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data
        if user_id not in user_styles:
            user_styles[user_id] = {'styles': [], 'random': False}
        if data == "style_random":
            await query.answer(text="Включён режим случайного стиля!")
            user_styles[user_id]['styles'] = []
            user_styles[user_id]['random'] = True
            await query.edit_message_text(
                "Включён режим: 🎲 Случайный стиль. Теперь отправьте текст, либо просто напишите любой символ — и я сгенерирую пост на случайную тему и в случайном стиле!"
            )
            # Удаляем меню из user_data
            if 'menu_message_id' in context.user_data:
                del context.user_data['menu_message_id']
            return
        if data.startswith("style_"):
            style = data[6:]
            if style == "done":
                chosen = "🎲 Случайный стиль" if user_styles[user_id]['random'] else ", ".join(user_styles[user_id]['styles']) if user_styles[user_id]['styles'] else "нет"
                await query.answer()
                await query.edit_message_text(
                    f"Стили выбраны: {chosen}. Теперь отправьте текст для Threads-карусели."
                )
                # Удаляем меню из user_data
                if 'menu_message_id' in context.user_data:
                    del context.user_data['menu_message_id']
                return
            # Обычный стиль
            user_styles[user_id]['random'] = False
            if style in user_styles[user_id]['styles']:
                user_styles[user_id]['styles'].remove(style)
            else:
                user_styles[user_id]['styles'].append(style)
            await query.answer(text=f"{'Добавлен' if style in user_styles[user_id]['styles'] else 'Убран'}: {style}")
            # Только обновляем кнопки, текст не трогаем!
            keyboard = [
                [InlineKeyboardButton(f"{'✅ ' if s[1] in user_styles[user_id]['styles'] else ''}{s[0]}", callback_data=f"style_{s[1]}") for s in STYLES[:3]],
                [InlineKeyboardButton(f"{'✅ ' if s[1] in user_styles[user_id]['styles'] else ''}{s[0]}", callback_data=f"style_{s[1]}") for s in STYLES[3:]],
                [InlineKeyboardButton("🎲 Случайный стиль", callback_data="style_random"), InlineKeyboardButton("Готово", callback_data="style_done")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=reply_markup)
            return
    except Exception:
        await update.effective_message.reply_text("Извините, ошибка, уже чиним. Свяжитесь с администратором")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        now_month = datetime.now().strftime("%Y-%m")
        user = get_user(user_id)
        if not user:
            update_user(user_id, last_reset=now_month)
            user = get_user(user_id)
        plan, used, last_reset = user
        if last_reset != now_month:
            reset_monthly_usage(user_id)
            used = 0
        if user_id in ADMIN_IDS:
            unlimited = True
        else:
            unlimited = False
        limit = PRO_LIMIT if plan == "pro" else FREE_LIMIT
        if not unlimited and used >= limit:
            pay_url = "https://donate.stream/yoomoney4100119217985005"
            text = (
                f"Лимит генераций по вашему тарифу исчерпан ({limit} в месяц).\n\n"
                "Чтобы продолжить пользоваться ботом, оплатите подписку по ссылке ниже:"
            )
            keyboard = [
                [InlineKeyboardButton("Оплатить", url=pay_url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            # Удаляем меню, если оно есть
            if 'menu_message_id' in context.user_data:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=update.effective_chat.id,
                        message_id=context.user_data['menu_message_id'],
                        reply_markup=None
                    )
                except Exception:
                    pass
                del context.user_data['menu_message_id']
            return
        msg = update.message
        if msg.forward_from_chat or msg.forward_from:
            content = msg.text or msg.caption
            if content is None:
                content = ""
            if not content:
                await update.message.reply_text("В пересланном сообщении нет текста.")
                return
        else:
            content = msg.text
            if content is None:
                content = ""
        await update.message.reply_text("Генерирую Threads-карусель...")
        # --- RAG: ищем релевантные посты и добавляем их в prompt ---
        if len(content.strip()) < 2:
            rag_results = []
        else:
            rag_results = get_rag_results(content, k=3)
        # Формируем few-shot из найденных постов (input/output)
        few_shot_messages = []
        for post in rag_results:
            # Пытаемся выделить input/output из текста поста
            # Если пост — это строка, ищем разделитель
            if isinstance(post, dict):
                input_text = post.get('input', '')
                output_text = post.get('output', '')
            else:
                # Если это строка, делим по '---' или используем весь текст
                parts = post.split('---')
                input_text = parts[0].strip()
                output_text = parts[1].strip() if len(parts) > 1 else ''
            if input_text and output_text:
                few_shot_messages.append({"role": "user", "content": input_text})
                few_shot_messages.append({"role": "assistant", "content": output_text})
        # Получаем выбранные стили пользователя
        user_data = user_styles.get(user_id, {'styles': [], 'random': False})
        selected_styles = user_data.get('styles', [])
        is_random = user_data.get('random', False)
        if is_random:
            prompt_for_log = "Случайный стиль: сгенерируй абсолютно случайный пост-карусель на любую тему и в любом стиле."
            result = threadsify_text(
                "Сгенерируй абсолютно случайный пост-карусель на любую тему и в любом стиле, как будто пользователь выбрал режим 'Случайный стиль'.",
                few_shot_messages=few_shot_messages,
                selected_styles=None
            )
        else:
            prompt_for_log = content
            result = threadsify_text(content, few_shot_messages=few_shot_messages, selected_styles=selected_styles)
        # --- конец вставки RAG ---
        if not unlimited:
            increment_usage(user_id)
        slides = [s.strip() for s in result.split('\n') if s.strip()]
        # Отправляем все слайды одним сообщением с отступами
        slides_text = '\n\n'.join(slides)
        await update.message.reply_text(f"```\n{slides_text}\n```", parse_mode="MarkdownV2")
        # После генерации очищаем выбранные стили
        if user_id in user_styles:
            del user_styles[user_id]
        # Удаляем меню, если оно есть
        if 'menu_message_id' in context.user_data:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data['menu_message_id'],
                    reply_markup=None
                )
            except Exception:
                pass
            del context.user_data['menu_message_id']
        # Снова показываем меню выбора стилей для следующего поста
        keyboard = [
            [InlineKeyboardButton(text, callback_data=f"style_{value}") for text, value in STYLES[:3]],
            [InlineKeyboardButton(text, callback_data=f"style_{value}") for text, value in STYLES[3:]],
            [InlineKeyboardButton("🎲 Случайный стиль", callback_data="style_random"), InlineKeyboardButton("Готово", callback_data="style_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        menu_msg = await update.message.reply_text("Выберите стили для следующего поста (можно несколько):", reply_markup=reply_markup)
        context.user_data['menu_message_id'] = menu_msg.message_id
        # Логируем взаимодействие
        log_interaction(user_id, prompt_for_log, selected_styles if not is_random else 'random', result)
    except Exception:
        await update.message.reply_text("Извините, ошибка, уже чиним. Свяжитесь с администратором")

async def pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Нет доступа.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Используй: /pro user_id")
        return
    target_id = int(context.args[0])
    update_user(target_id, plan="pro")
    await update.message.reply_text(f"Пользователь {target_id} переведён на Pro.")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Нет доступа.")
        return
    try:
        await update.message.chat.send_action(action=ChatAction.UPLOAD_DOCUMENT)
        with open(LOG_PATH, "rb") as f:
            await update.message.reply_document(f, filename="logs.txt")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке лога: {e}")

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pro", pro_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CallbackQueryHandler(style_callback, pattern=r"^style_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main() 
