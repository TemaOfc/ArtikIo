import pymorphy2

morph = pymorphy2.MorphAnalyzer()

def normalize_word(word):
    parsed = morph.parse(word.lower())[0]
    return parsed.normal_form

def is_close_word(guess, target):
    guess_normalized = normalize_word(guess)
    target_normalized = normalize_word(target)

    if guess_normalized == target_normalized:
        return True

    guess_parsed = morph.parse(guess.lower())[0]
    target_parsed = morph.parse(target.lower())[0]

    guess_lexeme = set([w.normal_form for w in guess_parsed.lexeme])
    target_lexeme = set([w.normal_form for w in target_parsed.lexeme])

    if guess_lexeme & target_lexeme:
        return True

    if len(guess_normalized) >= 4 and len(target_normalized) >= 4:
        if guess_normalized[:4] == target_normalized[:4]:
            return True

    return False

def check_guess(guess, target):
    # Нормализация: убираем пробелы, приводим к нижнему регистру
    guess = ' '.join(guess.strip().lower().split())
    target = ' '.join(target.strip().lower().split())

    # Проверка полного совпадения
    if guess == target:
        return {"result": "correct"}

    # Проверка частичного совпадения (для многословных фраз)
    target_parts = target.split()
    if len(target_parts) > 1:
        # Проверяем, является ли guess одной из частей target
        for part in target_parts:
            if guess == part:
                return {"result": "partial", "word": part}
            # Проверяем близкое совпадение с частью
            if is_close_word(guess, part):
                return {"result": "partial_close", "word": part}

    # Проверка близкого совпадения для полного слова
    if is_close_word(guess, target):
        return {"result": "close"}

    return {"result": "wrong"}
