# -*- coding: utf-8 -*-
"""
Логика сопоставления списка продуктов пользователя с рецептами.

Идея: пользователь пишет продукты свободным текстом,
бот нормализует их (приводит словоформы к корню) и ищет рецепт,
где бОльшая часть ключевых ингредиентов совпадает.
"""
import importlib.util
import os
import re
import unicodedata

# ---------------------------------------------------------------------------
# Загрузка базы рецептов из data/recipes.py по файловому пути.
# Это надёжнее, чем `from data import recipes` — на некоторых хостингах
# имя `data` конфликтует со встроенными модулями Python, и падает ImportError.
# ---------------------------------------------------------------------------
_RECIPES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "recipes.py")


def _load_recipes():
    if os.path.exists(_RECIPES_PATH):
        spec = importlib.util.spec_from_file_location("recipes", _RECIPES_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.BUNDLE
    # Резервный вариант (например, запуск из пакета easy_bot)
    try:
        from easy_bot.data import recipes as _data
        return _data.BUNDLE
    except ImportError:
        from .data import recipes as _data
        return _data.BUNDLE


_data_bundle = _load_recipes()


# ---------------------------------------------------------------------------
# Нормализация русских словоформ: приводим слово к "грубому корню".
# Убираем типичные окончания существительных мн. числа и падежей,
# чтобы "сыр", "сыра", "сыром", "сыры" -> "сыр".
# ---------------------------------------------------------------------------
_STRIP_ENDINGS = (
    "овым", "евой", "ая", "ую", "ый", "ий", "ой",
    "ами", "ями", "ом", "ем", "ам", "ям",
    "ах", "ях", "ах", "ов", "ев",
    "ы", "и", "у", "ю", "а", "я", "е", "о",
    "й", "ь",
)


def norm_word(word: str) -> str:
    """Приводит слово к нормализованной форме (в нижнем регистре, убрав бОльшую часть окончаний)."""
    w = word.strip().lower()
    w = unicodedata.normalize("NFKC", w)
    w = re.sub(r"[`']", "", w)
    # "колбаса/колбасу/колбасы" -> "колбас"
    for ending in _STRIP_ENDINGS:
        if len(w) > 4 and w.endswith(ending):
            stem = w[: -len(ending)]
            if len(stem) >= 2:
                w = stem
                break
    return w


def split_products(text: str) -> list:
    """Разбивает введённый текст на отдельные продукты (по запятым, союзам, пробелам с числами)."""
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)  # убираем скобки
    text = re.sub(r"\bи\b|\bс\b|\bсо\b|\bбез\b|\bплюс\b|\bтакже\b|\bещё\b|\bдай\b|\bимею\b|\bесть\b|\bесть:\b", " ", text)
    text = re.sub(r"\d+", " ", text)
    parts = re.split(r"[,;:/\n]+", text)
    words = []
    for part in parts:
        for chunk in part.split():
            # отбрасываем числа и короткий мусор
            if re.fullmatch(r"\d+|\(|\)", chunk):
                continue
            words.append(chunk)
    return words


def normalize_text(text: str) -> set:
    """Возвращает множество нормализованных корней для всего текста (одно- и двусловные)."""
    raw_words = split_products(text)
    result = set()
    # одиночные слова
    for w in raw_words:
        if len(w) < 2:
            continue
        result.add(norm_word(w))
    # пары слов (чтобы уловить "сливочное масло", "листья салата")
    for i in range(len(raw_words) - 1):
        pair = f"{norm_word(raw_words[i])} {norm_word(raw_words[i + 1])}"
        if len(raw_words[i]) >= 3 and len(raw_words[i + 1]) >= 3:
            result.add(pair)
    return result


def normalize_ingredients(ingredients: list) -> list:
    """Нормализует список ингредиентов рецепта (корни одно- и двусловных)."""
    out = []
    for ing in ingredients:
        out.append(norm_word(ing))
        if " " in ing:
            out.append(ing.replace(" ", " "))
    return out


# Перед сопоставлением нормализуем базу рецептов один раз.
_RECIPE_NORMS = []
for rec in _data_bundle:
    _RECIPE_NORMS.append(
        {
            "orig": rec,
            "norms": set(normalize_ingredients(rec["ingredients"])),
        }
    )


def _matches(text_norms: set, ing_norms: set) -> int:
    """Сколько ингредиентов рецепта задетектили в введённом тексте."""
    count = 0
    for ing in ing_norms:
        # точное совпадение или входит в корень
        for tn in text_norms:
            if ing == tn or (ing and tn.startswith(ing)) or (ing and ing.startswith(tn) and len(tn) >= 4):
                count += 1
                break
    return count


def recommend(text: str, top: int = 5) -> list:
    """Возвращает список рецептов [(рецепт, количество совпавших ингредиентов, доля), ...]."""
    text_norms = normalize_text(text)
    if not text_norms:
        return []
    scored = []
    for item in _RECIPE_NORMS:
        cnt = _matches(text_norms, item["norms"])
        if cnt > 0:
            fraction = cnt / len(item["norms"]) if item["norms"] else 0
            scored.append((item["orig"], cnt, fraction))
    scored.sort(key=lambda x: (x[2], x[1]), reverse=True)
    seen = set()
    out = []
    for rec, cnt, frac in scored:
        if rec["name"] not in seen:
            seen.add(rec["name"])
            out.append((rec, cnt, frac))
        if len(out) >= top:
            break
    return out


def describe_match(rec, cnt, frac) -> str:
    """Собирает красивую карточку рецепта для отправки пользователю."""
    cat_symbols = {
        "бутерброд": "🥪",
        "закуска": "🧀",
        "сытное блюдо": "🍲",
        "вкусняшка": "🍫",
        "завтрак": "🌅",
    }
    sym = cat_symbols.get(rec["category"], "🍽")
    diff = {1: "Просто", 2: "Норм", 3: "С опытом"}[rec.get("difficulty", 1)]
    match_pct = int(round(frac * 100))
    lines = [
        f"{sym} {rec['name']}",
        f"⏱ {rec['time_min']} мин · {diff} · совпадение {match_pct}%",
        "",
    ]
    for i, step in enumerate(rec["steps"], 1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)