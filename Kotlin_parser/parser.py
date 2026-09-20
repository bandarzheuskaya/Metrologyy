from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int = 0
    end: int = 0


@dataclass
class HalsteadResult:
    operators: Counter[str]
    operands: Counter[str]
    eta1: int
    eta2: int
    n1: int
    n2: int
    eta: int
    length: int
    volume: float


KEYWORDS_AS_OPERATORS = {
    "as", "as?", "break", "import", "where", "by", "catch", "class", "companion", "const", "constructor",
    "continue", "data", "do", "else", "enum", "finally", "for", "fun", "if", "in",
    "init", "interface", "is", "object", "package", "return", "super", "this", "throw",
    "try", "typealias", "val", "var", "when", "while", "abstract", "actual", "annotation",
    "crossinline", "expect", "external", "final", "infix", "inline", "inner", "internal",
    "lateinit", "noinline", "open", "operator", "out", "override", "private", "protected",
    "public", "reified", "sealed", "suspend", "tailrec", "vararg",
}

LITERAL_KEYWORDS = {"true", "false", "null"}

# Инфиксные функции Kotlin – аналоги And, Or, Xor, Shl, Shr, In из таблицы Холстеда.
INFIX_OPERATORS = {"and", "or", "xor", "shl", "shr", "ushr", "until", "downTo", "step", "to"}

# Ключевые слова, после которых @name – ссылка на метку.
LABEL_REF_KEYWORDS = {"return", "break", "continue", "this", "super"}
# Перед такими токенами имя со следующей за ним { – это объявление типа, а не вызов.
NOT_CALL_BEFORE_BRACE = {":", ",", "class", "object", "interface", "enum", "typealias"}
CONTROL_KEYWORDS = {"if", "for", "while", "when", "catch"}

TOKEN_RE = re.compile(
    r'(?P<RAW_STRING>"""[\s\S]*?""")'
    r'|(?P<STRING>"(?:\\.|[^"\\\n])*")'
    r"|(?P<CHAR>'(?:\\.|[^'\\\n])')"
    r'|(?P<NUMBER>'
    r'(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|0[oO][0-7_]+|'
    r'(?:\d[\d_]*\.\d[\d_]*|\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?)'
    r'[fFdDuUlL]*'
    r')'
    r'|(?P<BACKTICK>`[^`]+`)'
    r'|(?P<OP>===|!==|!!|\.\.<|\.\.|\?\.|\?:|::|->|'
    r'==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|'
    r'as\?)'
    r'|(?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<BRACKET>[(){}\[\]])'
    r'|(?P<SYMBOL>[+\-*/%=<>!&|^~?:.,;@])'
    r'|(?P<WS>\s+)'
    r'|(?P<OTHER>.)'
)

BRACKET_PAIRS = {"(": ")", "{": "}", "[": "]"}


def scan_string(src: str, start: int) -> int:
    """Возвращает индекс после закрывающей кавычки строки, начинающейся в src[start].

    Учитывает экранирование и вложенные строки внутри ${...}, например
    "a ${f("b")} c".
    """
    j = start + 1
    while j < len(src):
        char = src[j]
        if char == "\\":
            j += 2
        elif char == '"':
            return j + 1
        elif char == "\n":
            return j
        elif char == "$" and src[j + 1:j + 2] == "{":
            depth = 1
            j += 2
            while j < len(src) and depth:
                inner = src[j]
                if inner == '"':
                    j = scan_string(src, j)
                    continue
                if inner == "{":
                    depth += 1
                elif inner == "}":
                    depth -= 1
                j += 1
        else:
            j += 1
    return j


def strip_comments(code: str) -> str:
    """Удаляет // и вложенные /*...*/ комментарии, не изменяя Kotlin-литералы."""
    result: list[str] = []
    i = 0
    state = "code"
    nesting = 0

    while i < len(code):
        char = code[i]
        pair = code[i:i + 2]
        triple = code[i:i + 3]

        if state == "raw_string":
            if triple == '"""':
                result.append(triple)
                i += 3
                state = "code"
            else:
                result.append(char)
                i += 1
            continue

        if state == "string":
            result.append(char)
            if char == "\\" and i + 1 < len(code):
                result.append(code[i + 1])
                i += 2
            elif char == '"':
                state = "code"
                i += 1
            else:
                i += 1
            continue

        if state == "char":
            result.append(char)
            if char == "\\" and i + 1 < len(code):
                result.append(code[i + 1])
                i += 2
            elif char == "'":
                state = "code"
                i += 1
            else:
                i += 1
            continue

        if state == "block_comment":
            if pair == "/*":
                nesting += 1
                i += 2
            elif pair == "*/":
                nesting -= 1
                i += 2
                if nesting == 0:
                    state = "code"
            else:
                if char == "\n":
                    result.append("\n")
                i += 1
            continue

        if triple == '"""':
            result.append(triple)
            i += 3
            state = "raw_string"
        elif char == '"':
            end = scan_string(code, i)
            result.append(code[i:end])
            i = end
        elif char == "'":
            result.append(char)
            i += 1
            state = "char"
        elif pair == "//":
            i += 2
            while i < len(code) and code[i] != "\n":
                i += 1
        elif pair == "/*":
            state = "block_comment"
            nesting = 1
            i += 2
        else:
            result.append(char)
            i += 1

    return "".join(result)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(source):
        if source[pos] == '"' and not source.startswith('"""', pos):
            end = scan_string(source, pos)
            tokens.append(Token("STRING", source[pos:end], pos, end))
            pos = end
            continue
        match = TOKEN_RE.match(source, pos)
        kind = match.lastgroup
        if kind not in {"WS", "OTHER"}:
            tokens.append(Token(kind, match.group(), match.start(), match.end()))
        pos = match.end()
    return tokens


def is_identifier(token: Token) -> bool:
    return token.kind in {"IDENT", "BACKTICK"}


def is_literal(token: Token) -> bool:
    return token.kind in {"NUMBER", "STRING", "RAW_STRING", "CHAR"} or token.value in LITERAL_KEYWORDS


def is_infix_position(tokens: list[Token], i: int) -> bool:
    """Инфиксное слово стоит между двумя операндами: a and b, 1 until n, x shl (y)."""
    if i == 0 or i + 1 >= len(tokens):
        return False
    prev, nxt = tokens[i - 1], tokens[i + 1]
    left_ok = (
        (is_identifier(prev) and prev.value not in KEYWORDS_AS_OPERATORS)
        or is_literal(prev)
        or prev.value in {")", "]"}
    )
    right_ok = is_identifier(nxt) or is_literal(nxt) or nxt.value == "("
    return left_ok and right_ok


TYPE_ARG_SYMBOLS = {"<", ">", ",", "?", ".", "*"}


def generic_call_paren(tokens: list[Token], i: int) -> Optional[int]:
    """Для name<T, U>(...) возвращает индекс «(» после аргументов типов, иначе None."""
    if i + 1 >= len(tokens) or tokens[i + 1].value != "<":
        return None
    depth = 0
    for j in range(i + 1, len(tokens)):
        token = tokens[j]
        if token.value == "<":
            depth += 1
        elif token.value == ">":
            depth -= 1
            if depth == 0:
                nxt = tokens[j + 1] if j + 1 < len(tokens) else None
                return j + 1 if nxt is not None and nxt.value == "(" else None
        elif not (is_identifier(token) or token.value in TYPE_ARG_SYMBOLS):
            return None
    return None


def matching_bracket(tokens: list[Token], start: int) -> Optional[int]:
    opening = tokens[start].value
    closing = BRACKET_PAIRS.get(opening)
    if closing is None:
        return None

    depth = 0
    for i in range(start, len(tokens)):
        value = tokens[i].value
        if value == opening:
            depth += 1
        elif value == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def split_template_string(token: str) -> list[tuple[str, str]]:
    """Разделяет строковый шаблон Kotlin на текстовые части и выражения."""
    raw = token.startswith('"""')
    content = token[3:-3] if raw else token[1:-1]
    parts: list[tuple[str, str]] = []
    text: list[str] = []
    i = 0

    def flush() -> None:
        if text:
            parts.append(("text", '"' + "".join(text) + '"'))
            text.clear()

    while i < len(content):
        char = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else ""
        if char == "\\" and not raw and nxt:
            text.append(content[i:i + 2])  # \$ и другие escape-последовательности
            i += 2
        elif char == "$" and nxt == "{":
            depth = 1
            j = i + 2
            while j < len(content) and depth:
                inner = content[j]
                if inner == '"':
                    j = scan_string(content, j)
                    continue
                if inner == "{":
                    depth += 1
                elif inner == "}":
                    depth -= 1
                j += 1
            flush()
            parts.append(("expression", content[i + 2:j - 1 if depth == 0 else j]))
            i = j
        elif char == "$" and nxt.isascii() and (nxt.isalpha() or nxt == "_"):
            j = i + 1
            while j < len(content) and content[j].isascii() and (content[j].isalnum() or content[j] == "_"):
                j += 1
            flush()
            parts.append(("expression", content[i + 1:j]))
            i = j
        else:
            text.append(char)
            i += 1

    flush()
    return parts or [("text", token)]


def analyze_template_expression(expression: str, operators: list[str], operands: list[str]) -> None:
    expression_tokens = tokenize(strip_comments(expression))
    analyze_tokens(expression_tokens, operators, operands, analyze_templates=False)


def analyze_tokens(
    tokens: list[Token],
    operators: list[str],
    operands: list[str],
    analyze_templates: bool = True,
) -> None:
    stack: list[str] = []
    call_parens: set[int] = set()
    i = 0

    while i < len(tokens):
        token = tokens[i]
        value = token.value
        next_value = tokens[i + 1].value if i + 1 < len(tokens) else None
        prev_value = tokens[i - 1].value if i > 0 else None

        if is_literal(token):
            if analyze_templates and token.kind in {"STRING", "RAW_STRING"} and "$" in value:
                for part_type, part in split_template_string(value):
                    if part_type == "text":
                        operands.append(part)
                    else:
                        analyze_template_expression(part, operators, operands)
            else:
                operands.append(value)
            i += 1
            continue

        if is_identifier(token):
            if next_value == "@" and i + 1 < len(tokens) and tokens[i].end == tokens[i + 1].start:
                after_at = tokens[i + 2] if i + 2 < len(tokens) else None
                # return@label, break@label, continue@label, this@Outer: слово считаем, метку – нет
                if (
                    value in LABEL_REF_KEYWORDS
                    and after_at is not None
                    and is_identifier(after_at)
                    and tokens[i + 1].end == after_at.start
                ):
                    operators.append(value)
                    i += 3
                    continue
                # объявление метки loop@ – не считаем
                if value not in KEYWORDS_AS_OPERATORS and value not in LITERAL_KEYWORDS:
                    i += 2
                    continue

            if value in LITERAL_KEYWORDS:
                operands.append(value)
                i += 1
                continue

            if value in KEYWORDS_AS_OPERATORS:
                operators.append(value)
                if value in CONTROL_KEYWORDS and next_value == "(":
                    stack.append("control")
                    i += 2
                else:
                    i += 1
                continue

            if value in INFIX_OPERATORS and is_infix_position(tokens, i):
                operators.append(value)
                i += 1
                continue

            if next_value == "(":
                operators.append(f"{value}()")
                stack.append("call")
                i += 2
                continue

            paren = generic_call_paren(tokens, i)
            if paren is not None:
                operators.append(f"{value}()")  # вызов с аргументами типа: listOf<Int>(...)
                call_parens.add(paren)
                i += 1
                continue

            if next_value == "{" and prev_value not in NOT_CALL_BEFORE_BRACE:
                operators.append(f"{value}()")  # вызов с trailing lambda: run { ... }
                i += 1
                continue

            operands.append(value)
            i += 1
            continue

        if token.kind == "BRACKET":
            if value == "(":
                stack.append("call" if i in call_parens else "group")
            elif value == "{":
                stack.append("brace")
            elif value == "[":
                stack.append("square")
            else:
                opener = stack.pop() if stack else None
                if opener == "group":
                    operators.append("()")
                elif opener == "brace":
                    operators.append("{}")
                elif opener == "square":
                    operators.append("[]")
            i += 1
            continue

        if token.kind in {"OP", "SYMBOL"}:
            if value != ",":
                operators.append(value)
            i += 1
            continue

        i += 1


def compute_halstead(source: str) -> HalsteadResult:
    tokens = tokenize(strip_comments(source))
    operators: list[str] = []
    operands: list[str] = []
    analyze_tokens(tokens, operators, operands)

    operator_counts = Counter(operators)
    operand_counts = Counter(operands)
    eta1 = len(operator_counts)
    eta2 = len(operand_counts)
    n1 = sum(operator_counts.values())
    n2 = sum(operand_counts.values())
    eta = eta1 + eta2
    length = n1 + n2
    volume = length * math.log2(eta) if eta > 1 else 0.0

    return HalsteadResult(
        operators=operator_counts,
        operands=operand_counts,
        eta1=eta1,
        eta2=eta2,
        n1=n1,
        n2=n2,
        eta=eta,
        length=length,
        volume=volume,
    )


class HalsteadApp(tk.Tk if tk else object):
    def __init__(self) -> None:
        if tk is None:
            raise RuntimeError("Tkinter недоступен. Установите Python с поддержкой Tk.")
        super().__init__()
        self.title("Анализатор метрик Холстеда – Kotlin")
        self.geometry("1500x820")
        self.minsize(1100, 650)
        self._build_ui()

    def _build_ui(self) -> None:
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill=tk.X)
        ttk.Button(controls, text="Открыть .kt", command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(controls, text="Рассчитать метрики", command=self.calculate).pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text="Очистить", command=self.clear).pack(side=tk.LEFT)

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        source_frame = ttk.LabelFrame(main_pane, text="Исходный код Kotlin", padding=6)
        source_frame.rowconfigure(0, weight=1)
        source_frame.columnconfigure(0, weight=1)

        self.code_text = tk.Text(source_frame, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        self.code_text.bind("<Control-v>", self.paste_from_clipboard)
        self.code_text.bind("<Control-V>", self.paste_from_clipboard)
        self.code_text.bind("<Shift-Insert>", self.paste_from_clipboard)
        self.code_text.bind("<Button-3>", self.show_context_menu)

        source_y = ttk.Scrollbar(source_frame, orient=tk.VERTICAL, command=self.code_text.yview)
        source_x = ttk.Scrollbar(source_frame, orient=tk.HORIZONTAL, command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=source_y.set, xscrollcommand=source_x.set)
        self.code_text.grid(row=0, column=0, sticky="nsew")
        source_y.grid(row=0, column=1, sticky="ns")
        source_x.grid(row=1, column=0, sticky="ew")
        main_pane.add(source_frame, weight=1)

        result_frame = ttk.LabelFrame(main_pane, text="Базовые метрики Холстеда", padding=6)
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)

        columns = ("j", "operator", "f1", "i", "operand", "f2")
        self.table = ttk.Treeview(result_frame, columns=columns, show="headings", height=22)
        headings = {
            "j": "j",
            "operator": "Оператор",
            "f1": "f₁ⱼ",
            "i": "i",
            "operand": "Операнд",
            "f2": "f₂ᵢ",
        }
        widths = {"j": 42, "operator": 200, "f1": 80, "i": 42, "operand": 260, "f2": 80}
        for column in columns:
            self.table.heading(column, text=headings[column])
            anchor = tk.CENTER if column in {"j", "f1", "i", "f2"} else tk.W
            self.table.column(column, width=widths[column], anchor=anchor, stretch=True)

        self.table.tag_configure("total", background="#e8eef7", font=("Segoe UI", 10, "bold"))

        table_y = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.table.yview)
        table_x = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=self.table.xview)
        self.table.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        table_y.grid(row=0, column=1, sticky="ns")
        table_x.grid(row=1, column=0, sticky="ew")

        metrics_frame = ttk.LabelFrame(result_frame, text="Итоговые базовые и расширенные метрики", padding=8)
        metrics_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        metrics_frame.columnconfigure(1, weight=1)

        self.base_metrics_var = tk.StringVar(value="Базовые метрики будут показаны после анализа.")
        self.extended_metrics_var = tk.StringVar(value="Расширенные метрики будут показаны после анализа.")
        ttk.Label(metrics_frame, text="6 базовых метрик:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="nw")
        ttk.Label(metrics_frame, textvariable=self.base_metrics_var, justify=tk.LEFT).grid(row=0, column=1, sticky="w")
        ttk.Label(metrics_frame, text="3 расширенные метрики:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="nw", pady=(6, 0))
        ttk.Label(metrics_frame, textvariable=self.extended_metrics_var, justify=tk.LEFT).grid(row=1, column=1, sticky="w", pady=(6, 0))

        main_pane.add(result_frame, weight=1)

        self.status_var = tk.StringVar(value="Вставьте Kotlin-код в левую область и нажмите «Рассчитать метрики».")
        ttk.Label(self, textvariable=self.status_var, padding=(12, 8), justify=tk.LEFT).pack(fill=tk.X)

    def paste_from_clipboard(self, event=None) -> str:
        try:
            text = self.clipboard_get()
            if self.code_text.tag_ranges(tk.SEL):
                self.code_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.code_text.insert(tk.INSERT, text)
        except tk.TclError:
            pass
        return "break"

    def show_context_menu(self, event) -> str:
        self.code_text.focus_set()
        self.code_text.mark_set(tk.INSERT, f"@{event.x},{event.y}")

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Вырезать", command=lambda: self.code_text.event_generate("<<Cut>>"))
        menu.add_command(label="Копировать", command=lambda: self.code_text.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить", command=self.paste_from_clipboard)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: self.code_text.tag_add(tk.SEL, "1.0", tk.END))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите Kotlin-файл",
            filetypes=[("Kotlin files", "*.kt"), ("All files", "*.*")],
        )
        if not path:
            return

        for encoding in ("utf-8", "utf-8-sig", "cp1251"):
            try:
                with open(path, "r", encoding=encoding) as file:
                    source = file.read()
                self.code_text.delete("1.0", tk.END)
                self.code_text.insert("1.0", source)
                self.status_var.set(f"Загружен файл: {path}")
                return
            except UnicodeDecodeError:
                continue
            except OSError as error:
                messagebox.showerror("Ошибка открытия", str(error))
                return

        messagebox.showerror("Ошибка открытия", "Не удалось определить кодировку файла.")

    def calculate(self) -> None:
        source = self.code_text.get("1.0", tk.END).strip()
        if not source:
            messagebox.showwarning("Нет кода", "Введите Kotlin-код или откройте файл .kt.")
            return

        result = compute_halstead(source)
        self.table.delete(*self.table.get_children())

        operators = sorted(result.operators.items(), key=lambda item: (-item[1], item[0].lower()))
        operands = sorted(result.operands.items(), key=lambda item: (-item[1], item[0].lower()))
        row_count = max(len(operators), len(operands))

        for index in range(row_count):
            operator, f1 = operators[index] if index < len(operators) else ("", "")
            operand, f2 = operands[index] if index < len(operands) else ("", "")
            self.table.insert(
                "",
                tk.END,
                values=(
                    index + 1 if index < len(operators) else "",
                    operator,
                    f1,
                    index + 1 if index < len(operands) else "",
                    operand,
                    f2,
                ),
            )

        self.table.insert(
            "",
            tk.END,
            values=(
                "",
                f"η₁ = {result.eta1}",
                f"N₁ = {result.n1}",
                "",
                f"η₂ = {result.eta2}",
                f"N₂ = {result.n2}",
            ),
            tags=("total",),
        )

        self.base_metrics_var.set(
            f"η₁ = {result.eta1} – число различных операторов\n"
            f"N₁ = {result.n1} – общее число операторов\n"
            f"η₂ = {result.eta2} – число различных операндов\n"
            f"N₂ = {result.n2} – общее число операндов\n"
            f"f₁ⱼ – частоты операторов в таблице\n"
            f"f₂ᵢ – частоты операндов в таблице"
        )
        self.extended_metrics_var.set(
            f"η = η₁ + η₂ = {result.eta1} + {result.eta2} = {result.eta}\n"
            f"N = N₁ + N₂ = {result.n1} + {result.n2} = {result.length}\n"
            f"V = N × log₂(η) = {result.length} × log₂({result.eta}) = {result.volume:.2f} бит"
        )
        self.status_var.set(
            f"Анализ завершён: η₁={result.eta1}, N₁={result.n1}, η₂={result.eta2}, "
            f"N₂={result.n2}, η={result.eta}, N={result.length}, V={result.volume:.2f} бит."
        )

    def clear(self) -> None:
        self.code_text.delete("1.0", tk.END)
        self.table.delete(*self.table.get_children())
        self.base_metrics_var.set("Базовые метрики будут показаны после анализа.")
        self.extended_metrics_var.set("Расширенные метрики будут показаны после анализа.")
        self.status_var.set("Вставьте Kotlin-код в левую область и нажмите «Рассчитать метрики».")


if __name__ == "__main__":
    HalsteadApp().mainloop()
