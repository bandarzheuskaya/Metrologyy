fun readNumber(message: String): Int {
    println(message)

    while (true) {
        val text = readln()

        if (text.toIntOrNull() != null) {
            return text.toInt()
        } else {
            println("Введите целое число.")
        }
    }
}

fun calculateSum(first: Int, second: Int): Int {
    return first + second
}

fun determineSign(number: Int): String {
    return when {
        number > 0 -> "Положительное"
        number < 0 -> "Отрицательное"
        else -> "Ноль"
    }
}

fun main() {
    val first = readNumber("Введите первое число:")
    val second = readNumber("Введите второе число:")
    var sum = calculateSum(first, second)
    var counter = 0

    println("Сумма: $sum")
    println("Тип числа: ${determineSign(sum)}")

    for (value in 1..5) {
        if (value % 2 == 0 && value != 4) {
            sum += value
        } else {
            continue
        }
    }

    while (counter < 3) {
        sum -= counter
        counter++
    }

    do {
        println("Текущее значение: $sum")

        if (sum > 100 || sum < -100) {
            break
        }

        sum = sum / 2
    } while (sum != 0)

    println("Итог: $sum")
}