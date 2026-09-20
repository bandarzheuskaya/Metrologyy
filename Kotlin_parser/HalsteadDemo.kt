package demo

import kotlin.math.abs

const val LIMIT = 10

interface Shape { fun area(): Double }
enum class Color { RED, GREEN, BLUE }
data class Point(val x: Int, val y: Int)
open class Circle(private val r: Double) : Shape {
    override fun area(): Double = 3.14159 * r * r
}
object Counter { var total = 0; fun inc() { total++ } }

fun Int.isEven(): Boolean = this % 2 == 0
fun factorial(n: Int): Long {
    var result = 1L
    for (i in 2..n) result *= i
    return result
}
fun fib(n: Int): Int = if (n <= 1) n else fib(n - 1) + fib(n - 2)

fun classify(x: Any?): String = when (x) {
    null -> "null"
    is Int -> if (x > 0) "positive" else "non-positive"
    is String -> "string of ${x.length}"
    !is Double -> "other"
    else -> "double"
}

fun safeDiv(a: Int, b: Int): Int {
    try {
        if (a < 0) throw IllegalArgumentException("negative")
        return a / b
    } catch (e: ArithmeticException) {
        println("Error: ${e.message}")
        return 0
    } finally {
        Counter.inc()
    }
}
fun lengthOf(s: String?): Int = try { s!!.length } catch (e: NullPointerException) { -1 }
fun sumArray(arr: IntArray): Int {
    var s = 0
    var i = 0
    while (i < arr.size) {
        s += arr[i]
        i++
    }
    return s
}
fun bits(a: Int, b: Int): Int = (a and b) or (a xor b) shl 1

fun findPair(limit: Int): Point? {
    outer@ for (i in 1..limit) {
        for (j in limit downTo 1 step 2) {
            if (i * j == limit) return Point(i, j)
            if (i + j > limit * 2) break@outer
            if (j % 3 == 0) continue
        }
    }
    return null
}
fun <T> show(vararg items: T) {
    for (item in items) print("$item ")
    println()
}

fun main() {
    val n = (readlnOrNull() ?: "6").toIntOrNull() ?: 6
    val nums = intArrayOf(3, -1, 4, 1, -5, 9)
    val list = mutableListOf<Int>()
    var counter = 0
    do {
        list.add(counter * counter)
        counter += 2
    } while (counter < n)
    println("Squares: $list, sum = ${sumArray(nums)}")
    println("n! = ${factorial(n)}, fib(n) = ${fib(n)}")
    val grade = when (n) {
        in 1..3 -> "low"
        in 4..7 -> "mid"
        else -> "high"
    }
    val any: Any = if (n.isEven()) "even" else n
    val str = any as? String
    if (any is String && str != null) println(str.uppercase())
    else if (any !is String || n !in 0..LIMIT) println(any as Int + 1)
    val positive = nums.filter { it > 0 }.map { it * it }
    val total = nums.fold(0) { acc, v -> acc + abs(v) }
    val mul: (Int, Int) -> Int = { a, b -> a * b }
    val (px, py) = findPair(n * 2) ?: Point(0, 0)
    var flag = true
    for (c in Color.values()) if (c != Color.RED) flag = !flag
    show(grade, positive, total, mul(px, py))
    show(classify(null), classify(-5), classify("abc"), classify(2.5), classify('x'))
    show(safeDiv(10, 0), bits(6, 3), Circle(2.0).area(), listOf(1, 2, 3).map(::fib))
    show(1 shl 3, 20 shr 2, 7 xor 2, "k" to 1, flag && !flag || n >= 6, lengthOf(str))
    println(Counter.total)
}
