"""Тест системы весов слов и балансировки пар"""

from shared.words import get_random_word_pair
from shared.word_weights import get_word_weight

def test_word_pairs():
    """Тестируем генерацию сбалансированных пар слов"""

    print("=== Тест системы весов слов ===\n")

    # Генерируем 10 пар слов и проверяем баланс
    for i in range(10):
        pair = get_random_word_pair(['verbs', 'animals', 'food'])
        word1, word2 = pair[0], pair[1]
        weight1 = get_word_weight(word1)
        weight2 = get_word_weight(word2)
        total = weight1 + weight2

        print(f"Пара {i+1}:")
        print(f"  Слово 1: '{word1}' (вес: {weight1})")
        print(f"  Слово 2: '{word2}' (вес: {weight2})")
        print(f"  Сумма весов: {total}")

        # Проверяем логику балансировки
        if weight1 <= 2:
            expected = "тяжелое (4-5)"
            correct = weight2 >= 4
        elif weight1 == 3:
            expected = "среднее (3)"
            correct = weight2 == 3
        else:
            expected = "легкое (1-2)"
            correct = weight2 <= 2

        status = "OK" if correct else "FAIL"
        print(f"  Ожидалось: {expected} - {status}")
        print()

def test_verb_weights():
    """Проверяем, что глаголы действительно тяжелее существительных"""

    print("\n=== Проверка весов глаголов vs существительных ===\n")

    # Примеры пар: глагол vs существительное
    test_pairs = [
        ("гореть", "огонь"),
        ("бежать", "бег"),
        ("плавать", "вода"),
        ("летать", "птица"),
        ("думать", "мысль")
    ]

    for verb, noun in test_pairs:
        verb_weight = get_word_weight(verb)
        noun_weight = get_word_weight(noun)

        print(f"'{verb}' (глагол): {verb_weight}")
        print(f"'{noun}' (существительное): {noun_weight}")

        if verb_weight > noun_weight:
            print("OK - Глагол тяжелее существительного")
        else:
            print("FAIL - Глагол НЕ тяжелее существительного")
        print()

def test_points_calculation():
    """Демонстрируем расчет очков с учетом сложности"""

    print("\n=== Расчет очков с учетом сложности слова ===\n")

    from server.game_logic import GameRoom

    # Создаем тестовую комнату
    room = GameRoom("test", {'round_time': 60})

    # Симулируем отгадывание слов разной сложности
    test_words = [
        ("кот", 1),      # очень легкое
        ("собака", 1),   # очень легкое
        ("гореть", 3),   # среднее (глагол)
        ("думать", 4),   # сложное (глагол)
        ("профитроль", 4) # сложное (еда)
    ]

    for word, expected_weight in test_words:
        room.current_word = word
        actual_weight = get_word_weight(word)

        # Отгадывание через 10 секунд, первым игроком
        points = room.calculate_guesser_points(10, 1)

        print(f"Слово: '{word}'")
        print(f"  Вес: {actual_weight} (ожидалось: {expected_weight})")
        print(f"  Очки за отгадывание (10 сек, 1-й игрок): {points}")
        print()

if __name__ == "__main__":
    test_word_pairs()
    test_verb_weights()
    test_points_calculation()

    print("\n=== Тесты завершены ===")
