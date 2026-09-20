import kotlin.math.abs

const val MAX_SCORE = 100

// Чтение целого числа с консоли
fun readInt(prompt: String): Int {
    print(prompt)
    return readLine()?.toIntOrNull() ?: 0
}

// Сумма цифр числа
fun digitSum(number: Int): Int {
    var n = abs(number)
    var sum = 0
    do {
        sum += n % 10
        n /= 10
    } while (n > 0)
    return sum
}

// Поиск элемента в массиве
fun findIndex(arr: IntArray, target: Int): Int {
    var index = -1
    for (i in arr.indices) {
        if (arr[i] < 0 || arr[i] > 1000) continue
        if (arr[i] == target) {
            index = i
            break
        }
    }
    return index
}

// Деление с обработкой ошибок
fun safeDivide(a: Int, b: Int): Int {
    try {
        return a / b
    } catch (e: ArithmeticException) {
        println("Ошибка: деление на ноль")
        return 0
    } finally {
        println("Деление завершено")
    }
}

// Оценка по баллам
fun grade(score: Int): String {
    return when {
        score !in 0..MAX_SCORE -> "неверный балл"
        score >= 90 -> "отлично"
        score >= 75 && score < 90 -> "хорошо"
        score in 50..74 -> "удовлетворительно"
        else -> "неудовлетворительно"
    }
}

fun main() {
    val numbers = intArrayOf(12, 45, -7, 23, 56, 3, 89, 34)
    var running = true
    var attempts = 0

    while (running) {
        println("===== МЕНЮ =====")
        println("1 - Сумма цифр числа")
        println("2 - Поиск в массиве")
        println("3 - Деление с проверкой")
        println("4 - Оценка по баллам")
        println("0 - Выход")

        attempts++
        when (readInt("Выберите пункт: ")) {
            1 -> println("Сумма цифр = ${digitSum(readInt("Введите число: "))}")
            2 -> {
                val index = findIndex(numbers, readInt("Что искать: "))
                val text = if (index == -1) "не найден" else "индекс $index"
                println("Результат: $text")
            }
            3 -> {
                val a = readInt("Делимое: ")
                val b = readInt("Делитель: ")
                println("Частное = ${safeDivide(a, b)}")
            }
            4 -> println("Оценка: ${grade(readInt("Введите баллы: "))}")
            0 -> {
                running = false
                println("Завершение работы. Запросов: $attempts")
            }
            else -> {
                println("Неверный пункт меню, попробуйте снова.")
                continue
            }
        }
    }
}
