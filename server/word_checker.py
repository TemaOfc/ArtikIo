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

    if guess == target:
        return "correct"

    if is_close_word(guess, target):
        return "close"

    return "wrong"
