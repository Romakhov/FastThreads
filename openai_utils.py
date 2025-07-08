import openai
from config import OPENAI_API_KEY
import json
import random

client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.proxyapi.ru/openai/v1"
)


def load_examples_json(n=3):
    with open(EXAMPLES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    examples = random.sample(data, k=min(n, len(data)))
    return [(ex["input"], ex["output"]) for ex in examples]

def threadsify_text(user_text, few_shot_messages=None, selected_styles=None):
    system_prompt = (
        "Ты — автор вирусных постов в Threads. Пишешь короткие, цепкие тексты-карусели на актуальные темы. "
        "Стиль — живой, как будто пишет реальный пользователь Threads: немного уставший, ироничный, умный, но не занудный. "
        "Избегаешь пафоса, нравоучений, штампов и «подачи как у ИИ». Иногда добавляешь лёгкий абсурд или мемность. "
        "Каждый пост — это карусель: цепляющий хук, затем 3–6 коротких слайдов. Каждый слайд — 1–2 фразы. "
        "Пиши легко, узнаваемо, будто делишься своим наблюдением с другом. "
        "Не используй эмодзи и хэштеги. Не делай выводов вроде «вот и всё», «что думаете?» — просто закончи мыслью."
    )
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    if few_shot_messages:
        messages.extend(few_shot_messages)
    # Добавляем выбранные стили в prompt пользователя
    if selected_styles:
        styles_str = ', '.join(selected_styles)
        user_prompt = f"Пользователь выбрал стили: {styles_str}. {user_text}"
    else:
        user_prompt = user_text
    messages.append({"role": "user", "content": user_prompt})
    print("\n===== ОТПРАВЛЯЕМ В OpenAI =====")
    for m in messages:
        print(f"{m['role']}: {m['content']}")
    print("Параметры: model=gpt-4o, temperature=0.9, top_p=0.9, frequency_penalty=0.3, presence_penalty=0.4, max_tokens=500, n=2")
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.9,
        top_p=0.9,
        frequency_penalty=0.3,
        presence_penalty=0.4,
        max_tokens=500,
        messages=messages
    )
    # Fallback: выбираем лучший ответ по длине
    choices = response.choices
    best = max(choices, key=lambda c: len(c.message.content.strip()))
    print("===== ОТВЕТЫ OpenAI =====")
    for i, c in enumerate(choices, 1):
        print(f"Вариант {i}:\n{c.message.content.strip()}\n---")
    print(f"Выбранный вариант:\n{best.message.content.strip()}")
    return best.message.content.strip() 