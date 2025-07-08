import os
import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
import re

# Пропишите ваш OpenAI API ключ здесь (теперь только через переменные окружения)

POSTS_PATH = os.path.join(os.path.dirname(__file__), "posts.json")

def load_posts():
    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)
    docs = []
    for post in posts:
        if isinstance(post, str):
            text = post
            meta = {}
        elif isinstance(post, dict):
            text = " ".join(str(post.get(key, "")) for key in ("text", "output", "input"))
            meta = post
        else:
            text = ""
            meta = {}
        docs.append(Document(page_content=text, metadata=meta))
    return docs

def get_rag_results(query, k=3):
    docs = load_posts()
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(docs, embeddings)
    results = db.similarity_search(query, k=k)
    if not results:
        query_lower = query.lower()
        # Проверяем, ищет ли пользователь по категории или тегу
        category = None
        tags = None
        cat_match = re.search(r"category:([\wА-Яа-яЁё\- ]+)", query, re.IGNORECASE)
        tag_match = re.search(r"tag:([\wА-Яа-яЁё,\- ]+)", query, re.IGNORECASE)
        if cat_match:
            category = cat_match.group(1).strip().lower()
        if tag_match:
            tags = [t.strip().lower() for t in tag_match.group(1).split(",") if t.strip()]
        fallback = []
        for doc in docs:
            meta = doc.metadata
            # Поиск по тексту, если не задана категория/теги
            text_match = query_lower in doc.page_content.lower()
            cat_match = False
            tag_match = False
            if category and 'category' in meta and isinstance(meta['category'], str):
                cat_match = category in meta['category'].lower()
            if tags and 'tags' in meta and isinstance(meta['tags'], str):
                post_tags = [t.strip().lower() for t in meta['tags'].split(",") if t.strip()]
                tag_match = any(tag in post_tags for tag in tags)
            # Если явно ищем по категории/тегу — фильтруем только по ним
            if category or tags:
                if (not category or cat_match) and (not tags or tag_match):
                    fallback.append(doc)
            else:
                # Обычный поиск: ищем по тексту, категории и тегам
                in_cat = 'category' in meta and isinstance(meta['category'], str) and query_lower in meta['category'].lower()
                in_tags = 'tags' in meta and isinstance(meta['tags'], str) and any(query_lower in t for t in meta['tags'].lower().split(","))
                if text_match or in_cat or in_tags:
                    fallback.append(doc)
        return [doc.metadata for doc in fallback[:k]]
    return [doc.metadata for doc in results]

if __name__ == "__main__":
    # Пример ручного запуска
    query = "нейросети"
    results = get_rag_results(query, k=3)
    print("Релевантные посты:")
    for res in results:
        print("---")
        print(res)