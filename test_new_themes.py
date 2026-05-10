"""Тест новых тем: математика, физика, секс"""

from shared.words import get_random_word_pair, WORD_THEMES
from shared.word_weights import get_word_weight

def test_new_themes():
    """Проверяем что новые темы добавлены и работают"""

    print("=== Проверка новых тем ===\n")

    # Проверяем наличие тем
    themes = ['math', 'physics', 'sex']
    for theme in themes:
        if theme in WORD_THEMES:
            word_count = len(WORD_THEMES[theme])
            print(f"Тема '{theme}': {word_count} слов")
        else:
            print(f"ОШИБКА: Тема '{theme}' не найдена!")

    print("\n=== Примеры слов и их веса ===\n")

    # Математика
    print("МАТЕМАТИКА:")
    math_examples = ["число", "дискриминант", "интеграл", "теорема Гёделя", "квантор"]
    for word in math_examples:
        weight = get_word_weight(word)
        print(f"  '{word}': вес {weight}")

    # Физика
    print("\nФИЗИКА:")
    physics_examples = ["сила", "энтропия", "фотон", "черная дыра", "квантовая механика"]
    for word in physics_examples:
        weight = get_word_weight(word)
        print(f"  '{word}': вес {weight}")

    # Секс
    print("\nСЕКС:")
    sex_examples = ["тело", "либидо", "оргазм", "феромоны", "психосексуальное развитие"]
    for word in sex_examples:
        weight = get_word_weight(word)
        print(f"  '{word}': вес {weight}")

    print("\n=== Тест генерации пар слов ===\n")

    # Генерируем пары для каждой темы
    for theme in themes:
        print(f"\nТема: {theme}")
        for i in range(3):
            pair = get_random_word_pair([theme])
            word1, word2 = pair[0], pair[1]
            weight1 = get_word_weight(word1)
            weight2 = get_word_weight(word2)
            print(f"  Пара {i+1}: '{word1}' (вес {weight1}) + '{word2}' (вес {weight2}) = {weight1 + weight2}")

    print("\n=== Проверка балансировки ===\n")

    # Проверяем что балансировка работает
    for theme in themes:
        print(f"\nТема: {theme}")
        balanced_count = 0
        for i in range(10):
            pair = get_random_word_pair([theme])
            word1, word2 = pair[0], pair[1]
            weight1 = get_word_weight(word1)
            weight2 = get_word_weight(word2)

            # Проверяем логику балансировки
            if weight1 <= 2:
                expected = weight2 >= 4
            elif weight1 == 3:
                expected = weight2 == 3
            else:
                expected = weight2 <= 2

            if expected:
                balanced_count += 1

        print(f"  Сбалансированных пар: {balanced_count}/10")

    print("\n=== Тест завершен ===")

if __name__ == "__main__":
    test_new_themes()
