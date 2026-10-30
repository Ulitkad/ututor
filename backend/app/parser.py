"""Strict, lossless parsing of the three human-readable import formats."""
import re

from .stress import VOWELS, automatic_stress

CATEGORIES = {"stress": "Орфоэпия", "spelling": "Орфография", "grammar": "Грамматические нормы"}


class ParseError(ValueError):
    pass


def parse_stress(source):
    acute = None
    if "\u0301" in source:
        if source.count("\u0301") != 1:
            raise ParseError("Отметьте только одно ударение.")
        acute = source.index("\u0301") - 1
        source = source.replace("\u0301", "")
        if acute < 0 or source[acute].lower() not in VOWELS:
            raise ParseError("Знак ударения должен стоять после гласной.")
    if not re.fullmatch(r"[а-яА-ЯёЁ-]+", source):
        raise ParseError("Введите одно русское слово; ударная гласная — заглавная.")
    word = source.lower()
    vowels = [i for i, c in enumerate(word) if c in VOWELS]
    if not vowels:
        raise ParseError("В слове нет гласных.")
    marked = [i for i, c in enumerate(source) if c.lower() in VOWELS and c.isupper()]
    # Title case (Остановка) is ordinary input, not a first-vowel marker.
    # An acute accent resolves that ambiguity for initial stressed vowels.
    if len(marked) > 1:
        raise ParseError("Отметьте только одну ударную гласную.")
    title_case = source[0].isupper() and source[1:] == source[1:].lower()
    stress = acute if acute is not None else marked[0] if marked and not title_case else None
    if stress is None:
        stress = vowels[0] if len(vowels) == 1 else automatic_stress(word)
    return {"word": word, "stress": stress}, stress is None


def parse_gaps(source, category):
    parts = []
    end = 0
    for match in re.finditer(r"\(([^()]*)\)", source):
        text = source[end:match.start()]
        if "(" in text or ")" in text:
            raise ParseError("Проверьте парность скобок.")
        if text:
            parts.append({"text": text})
        inner = match.group(1)
        hint = ""
        if category == "grammar":
            if inner.count("|") != 1:
                raise ParseError("Укажите подсказку и варианты: (сберечь|сбережёт,сберегёт).")
            hint, inner = inner.split("|")
            hint = hint.strip()
            if not hint:
                raise ParseError("Начальная форма не может быть пустой.")
        elif "|" in inner:
            raise ParseError("Для орфографии используйте варианты через запятую без |.")
        options = [normalize_option(v) if category == "spelling" else v.strip() for v in inner.split(",")]
        if len(options) < 2:
            raise ParseError("Укажите верный ответ и хотя бы один ложный вариант.")
        if category == "grammar" and any(not o for o in options):
            raise ParseError("Словоформа не может быть пустой.")
        if len(set(options)) != len(options):
            raise ParseError("Варианты ответа не должны повторяться.")
        parts.append({"hint": hint, "options": options, "correct": options[0]})
        end = match.end()
    tail = source[end:]
    if "(" in tail or ")" in tail:
        raise ParseError("Проверьте парность скобок.")
    if tail:
        parts.append({"text": tail})
    if not any("options" in p for p in parts):
        raise ParseError("Добавьте хотя бы один пропуск с вариантами ответа.")
    if sum("options" in p for p in parts) > 100:
        raise ParseError("В задании может быть не более 100 пропусков.")
    return {"parts": parts}, False


def normalize_option(value):
    return " " if value and value.isspace() else value.strip()


def parse_lines(raw, category):
    if category not in CATEGORIES:
        raise ParseError("Неизвестная категория.")
    if len(raw.encode("utf-8")) > 1024 * 1024:
        raise ParseError("Максимальный размер списка — 1 МБ.")
    lines = [(i, s.strip()) for i, s in enumerate(raw.lstrip("\ufeff").splitlines(), 1) if s.strip()]
    if not lines:
        raise ParseError("Добавьте хотя бы одно задание.")
    if len(lines) > 3000:
        raise ParseError("В одном списке может быть не более 3000 заданий.")
    result, errors = [], []
    for index, source in lines:
        try:
            if len(source) > 2000:
                raise ParseError("Строка слишком длинная (максимум 2000 символов).")
            explanations = []

            def extract_explanation(match):
                value = match[1].strip()
                if not value:
                    raise ParseError("Пояснение в квадратных скобках не может быть пустым.")
                explanations.append(value)
                return ""

            body = re.sub(r"\[([^\[\]]*)\]", extract_explanation, source).strip()
            if "[" in body or "]" in body:
                raise ParseError("Проверьте парность квадратных скобок; вложенные пояснения не допускаются.")
            data, review = parse_stress(body) if category == "stress" else parse_gaps(body, category)
            if explanations:
                data["explanation"] = "; ".join(explanations)
            result.append({"source": source, "data": data, "needs_review": review})
        except ParseError as exc:
            errors.append({"line": index, "message": str(exc)})
    if errors:
        raise ParseError("\n".join(f"Строка {e['line']}: {e['message']}" for e in errors[:20]))
    return result


def solution(data):
    if "word" in data:
        i = data["stress"]
        return data["word"] if i is None else data["word"][:i + 1] + "\u0301" + data["word"][i + 1:]
    return "".join(p["text"] if "text" in p else p["correct"] for p in data["parts"])
