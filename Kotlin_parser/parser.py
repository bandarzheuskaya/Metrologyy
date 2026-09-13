import math
import re
from collections import Counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


SYMBOL_OPERATORS = {
    "!==", "===", ">>=", "<<=", ">>", "<<", "..", "?.", "?:", "::", "->",
    ">=", "<=", "==", "!=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=", "%=",
    "=", "+", "-", "*", "/", "%", ">", "<", "!", ".", ";", ",", ":"
}

# Самостоятельные управляющие/служебные операторы.
SIMPLE_KEYWORDS = {"break", "continue", "return", "throw", "is", "as", "as?"}

# Слова объявлений не считаются операторами или операндами в данной адаптации.
DECLARATION_WORDS = {
    "package", "import", "fun", "class", "data", "enum", "interface", "object", "typealias",
    "val", "var", "const", "open", "override", "private", "public", "protected", "internal",
    "abstract", "sealed", "companion", "operator", "inline", "tailrec", "suspend", "out"
}

TYPE_NAMES = {
    "Int", "Long", "Short", "Byte", "Double", "Float", "Boolean", "Char", "String", "Unit",
    "Any", "Nothing", "List", "MutableList", "Set", "MutableSet", "Map", "MutableMap", "Array",
    "Number", "Comparable", "Iterable", "Exception", "Throwable", "RuntimeException"
}

TOKEN_RE = re.compile(
    r'"""[\s\S]*?"""'
    r'|"(?:\\.|[^"\\])*"'
    r"|'(?:\\.|[^'\\])*'"
    r"|\b\d+(?:\.\d+)?(?:[fFL])?\b"
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|!==|===|>>=|<<=|>>|<<|\.\.|\?\.|\?:|::|->|>=|<=|==|!=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|%="
    r"|[=+\-*/%><!.,:(){}\[\];?]"
)

TEMPLATE_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)|\$\{(.*?)\}", re.DOTALL)


def remove_comments(code: str) -> str:
    """Удаляет комментарии Kotlin, сохраняя строковые и символьные литералы."""
    result = []
    index = 0
    in_string = False
    in_char = False
    in_triple_string = False
    escaped = False

    while index < len(code):
        current = code[index]
        pair = code[index:index + 2]
        triple = code[index:index + 3]

        if in_triple_string:
            if triple == '\"\"\"':
                result.append('\"\"\"')
                index += 3
                in_triple_string = False
            else:
                result.append(current)
                index += 1
            continue

        if in_string:
            result.append(current)
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == '"':
                in_string = False
            index += 1
            continue

        if in_char:
            result.append(current)
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == "'":
                in_char = False
            index += 1
            continue

        if triple == '\"\"\"':
            result.append('\"\"\"')
            index += 3
            in_triple_string = True
        elif current == '"':
            result.append(current)
            index += 1
            in_string = True
        elif current == "'":
            result.append(current)
            index += 1
            in_char = True
        elif pair == "//":
            index += 2
            while index < len(code) and code[index] != "\n":
                index += 1
        elif pair == "/*":
            index += 2
            level = 1
            while index < len(code) and level > 0:
                if code[index:index + 2] == "/*":
                    level += 1
                    index += 2
                elif code[index:index + 2] == "*/":
                    level -= 1
                    index += 2
                else:
                    index += 1
        else:
            result.append(current)
            index += 1

    return "".join(result)


def remove_package_and_import(code: str) -> str:
    return "\n".join(
        line for line in code.splitlines()
        if not line.strip().startswith("package ") and not line.strip().startswith("import ")
    )


def is_identifier(token: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) is not None


def is_literal(token: str) -> bool:
    return (
        re.fullmatch(r"\d+(?:\.\d+)?(?:[fFL])?", token) is not None
        or (len(token) >= 2 and token[0] == '"' and token[-1] == '"')
        or (len(token) >= 2 and token[0] == "'" and token[-1] == "'")
        or token in {"true", "false", "null"}
    )


def find_matching(tokens, start, opening, closing):
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == opening:
            depth += 1
        elif tokens[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def is_declaration_name(tokens, index):
    return index > 0 and tokens[index - 1] in {
        "fun", "class", "interface", "object", "enum", "typealias"
    }


def split_template_string(token: str):
    """
    Делит Kotlin-шаблон строки на текстовые константы и выражения.
    Пример: "Сумма: $sum" -> ["Сумма: ", "sum"].
    Пустые текстовые части не возвращаются.
    """
    if token.startswith('\"\"\"') and token.endswith('\"\"\"'):
        content = token[3:-3]
    else:
        content = token[1:-1]

    parts = []
    position = 0
    for match in TEMPLATE_RE.finditer(content):
        text_part = content[position:match.start()]
        if text_part:
            parts.append(("text", f'"{text_part}"'))

        simple_name = match.group(1)
        expression = match.group(2)
        if simple_name is not None:
            parts.append(("expression", simple_name))
        else:
            parts.append(("expression", expression))
        position = match.end()

    tail = content[position:]
    if tail:
        parts.append(("text", f'"{tail}"'))

    # Если строка состоит только из ${...}, текстовых частей нет.
    if not parts:
        parts.append(("text", token))

    return parts


def find_control_operators(tokens):
    """Объединяет составные управляющие конструкции Kotlin в единые операторы."""
    operators = []
    skipped = set()
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token == "if":
            condition_end = index
            if index + 1 < len(tokens) and tokens[index + 1] == "(":
                found = find_matching(tokens, index + 1, "(", ")")
                if found is not None:
                    condition_end = found

            body_end = condition_end
            if condition_end + 1 < len(tokens) and tokens[condition_end + 1] == "{":
                found = find_matching(tokens, condition_end + 1, "{", "}")
                if found is not None:
                    body_end = found

            has_else = body_end + 1 < len(tokens) and tokens[body_end + 1] == "else"
            operators.append("if ... else" if has_else else "if")
            skipped.add(index)
            if has_else:
                skipped.add(body_end + 1)
            index += 1
            continue

        if token == "for":
            operators.append("for ... in")
            skipped.add(index)
            if index + 1 < len(tokens) and tokens[index + 1] == "(":
                end = find_matching(tokens, index + 1, "(", ")")
                if end is not None:
                    for position in range(index + 2, end):
                        if tokens[position] == "in":
                            skipped.add(position)
                            break
            index += 1
            continue

        if token == "do":
            operators.append("do ... while")
            skipped.add(index)
            if index + 1 < len(tokens) and tokens[index + 1] == "{":
                body_end = find_matching(tokens, index + 1, "{", "}")
                if body_end is not None and body_end + 1 < len(tokens and tokens):
                    if tokens[body_end + 1] == "while":
                        skipped.add(body_end + 1)
            index += 1
            continue

        if token == "when":
            operators.append("when")
            skipped.add(index)
            index += 1
            continue

        if token == "try":
            label = "try"
            skipped.add(index)
            position = index + 1

            if position < len(tokens) and tokens[position] == "{":
                body_end = find_matching(tokens, position, "{", "}")
                if body_end is not None:
                    position = body_end + 1

                    if position < len(tokens) and tokens[position] == "catch":
                        label = "try ... catch"
                        skipped.add(position)
                        position += 1
                        if position < len(tokens) and tokens[position] == "(":
                            args_end = find_matching(tokens, position, "(", ")")
                            if args_end is not None:
                                position = args_end + 1
                        if position < len(tokens) and tokens[position] == "{":
                            catch_end = find_matching(tokens, position, "{", "}")
                            if catch_end is not None:
                                position = catch_end + 1

                    if position < len(tokens) and tokens[position] == "finally":
                        label = "try ... catch ... finally" if "catch" in label else "try ... finally"
                        skipped.add(position)

            operators.append(label)
            index += 1
            continue

        index += 1

    return operators, skipped


def analyze_template_expression(expression: str):
    """Анализирует содержимое ${...} как обычное Kotlin-выражение."""
    tokens = TOKEN_RE.findall(expression)
    operators = []
    operands = []
    skip_parentheses = set()

    for index, token in enumerate(tokens):
        if token == "(" and index > 0 and is_identifier(tokens[index - 1]):
            skip_parentheses.add(index)
            closing = find_matching(tokens, index, "(", ")")
            if closing is not None:
                skip_parentheses.add(closing)

    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""

        if token in SYMBOL_OPERATORS:
            operators.append(token)
        elif token == "(" and index not in skip_parentheses:
            operators.append("( )")
        elif token in {"(", ")", "{", "}", "[", "]", "?"}:
            continue
        elif token in SIMPLE_KEYWORDS:
            operators.append(token)
        elif token in DECLARATION_WORDS or token in TYPE_NAMES:
            continue
        elif is_literal(token):
            operands.append(token)
        elif is_identifier(token):
            if following == "(":
                operators.append(f"{token}()")
            else:
                operands.append(token)

    return operators, operands


def analyze_kotlin(code: str):
    clean_code = remove_package_and_import(remove_comments(code))
    tokens = TOKEN_RE.findall(clean_code)

    operators, control_skip = find_control_operators(tokens)
    operands = []
    skip_parentheses = set()

    # Скобки вызова функции входят в оператор имяФункции().
    for index, token in enumerate(tokens):
        if token == "(" and index > 0 and is_identifier(tokens[index - 1]):
            skip_parentheses.add(index)
            closing = find_matching(tokens, index, "(", ")")
            if closing is not None:
                skip_parentheses.add(closing)

    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""

        if index in control_skip:
            continue

        if token in SYMBOL_OPERATORS:
            operators.append(token)
            continue

        # Обычная пара скобок, выделяющая подвыражение, – один оператор ( ).
        if token in {"(", ")"}:
            if token == "(" and index not in skip_parentheses:
                operators.append("( )")
            continue

        # Фигурные и квадратные скобки не считаются отдельно.
        if token in {"{", "}", "[", "]", "?"}:
            continue

        if token in SIMPLE_KEYWORDS:
            operators.append(token)
            continue

        if token in DECLARATION_WORDS or token in TYPE_NAMES:
            continue

        if is_literal(token):
            # Обычная строка без $ – одна строковая константа-операнд.
            # В шаблоне строк текст и выражения учитываются раздельно.
            if token.startswith('"') and "$" in token:
                for part_type, part in split_template_string(token):
                    if part_type == "text":
                        operands.append(part)
                    else:
                        template_operators, template_operands = analyze_template_expression(part)
                        operators.extend(template_operators)
                        operands.extend(template_operands)
            else:
                operands.append(token)
            continue

        if is_identifier(token):
            if is_declaration_name(tokens, index):
                continue

            # Функция/метод вместе с круглыми скобками – единый оператор.
            if following == "(" and token not in {"if", "when", "for", "while", "catch"}:
                operators.append(f"{token}()")
            else:
                operands.append(token)

    operator_counts = Counter(operators)
    operand_counts = Counter(operands)

    eta1 = len(operator_counts)
    eta2 = len(operand_counts)
    total_operators = sum(operator_counts.values())
    total_operands = sum(operand_counts.values())
    vocabulary = eta1 + eta2
    length = total_operators + total_operands
    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0.0

    return (
        operator_counts,
        operand_counts,
        eta1,
        total_operators,
        eta2,
        total_operands,
        vocabulary,
        length,
        volume,
    )


class HalsteadApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Метрики Холстеда для Kotlin")
        self.geometry("1160x760")
        self.minsize(900, 620)
        self.create_widgets()

    def create_widgets(self):
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill=tk.X)

        ttk.Button(controls, text="Открыть .kt", command=self.open_file).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(controls, text="Рассчитать метрики", command=self.calculate).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="Очистить", command=self.clear).pack(side=tk.LEFT)

        ttk.Label(
            controls,
            text="Ctrl+V поддерживается. Шаблоны строк $name и ${...} анализируются."
        ).pack(side=tk.LEFT, padx=18)

        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        source_frame = ttk.LabelFrame(main_pane, text="Исходный Kotlin-код", padding=6)
        self.code_text = tk.Text(source_frame, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        source_scroll_y = ttk.Scrollbar(source_frame, orient=tk.VERTICAL, command=self.code_text.yview)
        source_scroll_x = ttk.Scrollbar(source_frame, orient=tk.HORIZONTAL, command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=source_scroll_y.set, xscrollcommand=source_scroll_x.set)
        self.code_text.grid(row=0, column=0, sticky="nsew")
        source_scroll_y.grid(row=0, column=1, sticky="ns")
        source_scroll_x.grid(row=1, column=0, sticky="ew")
        source_frame.rowconfigure(0, weight=1)
        source_frame.columnconfigure(0, weight=1)
        main_pane.add(source_frame, weight=3)

        result_frame = ttk.LabelFrame(main_pane, text="Таблица базовых метрик Холстеда", padding=6)
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)

        columns = ("j", "operator", "f1", "i", "operand", "f2")
        self.table = ttk.Treeview(result_frame, columns=columns, show="headings", height=13)
        headings = {
            "j": "j",
            "operator": "Оператор",
            "f1": "f₁ⱼ",
            "i": "i",
            "operand": "Операнд",
            "f2": "f₂ᵢ",
        }
        widths = {"j": 45, "operator": 280, "f1": 70, "i": 45, "operand": 360, "f2": 70}

        for column in columns:
            self.table.heading(column, text=headings[column])
            anchor = tk.CENTER if column in {"j", "f1", "i", "f2"} else tk.W
            self.table.column(column, width=widths[column], anchor=anchor)

        result_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.table.yview)
        self.table.configure(yscrollcommand=result_scroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        result_scroll.grid(row=0, column=1, sticky="ns")
        main_pane.add(result_frame, weight=3)

        self.summary = ttk.Label(
            self,
            text="Введите Kotlin-код и нажмите «Рассчитать метрики».",
            padding=(12, 8),
            justify=tk.LEFT,
        )
        self.summary.pack(fill=tk.X)



    def open_file(self):
        path = filedialog.askopenfilename(
            title="Выберите Kotlin-файл",
            filetypes=[("Kotlin files", "*.kt"), ("All files", "*.*")],
        )
        if not path:
            return

        for encoding in ("utf-8", "cp1251"):
            try:
                with open(path, "r", encoding=encoding) as file:
                    content = file.read()
                self.code_text.delete("1.0", tk.END)
                self.code_text.insert("1.0", content)
                return
            except UnicodeDecodeError:
                continue
            except OSError as error:
                messagebox.showerror("Ошибка открытия", str(error))
                return

        messagebox.showerror("Ошибка открытия", "Не удалось определить кодировку файла.")

    def calculate(self):
        code = self.code_text.get("1.0", tk.END).strip()
        if not code:
            messagebox.showwarning("Нет кода", "Введите Kotlin-код или откройте Kotlin-файл .kt.")
            return

        results = analyze_kotlin(code)
        operator_counts, operand_counts, eta1, n1, eta2, n2, vocabulary, length, volume = results

        for row in self.table.get_children():
            self.table.delete(row)

        operators = sorted(operator_counts.items(), key=lambda item: item[0].lower())
        operands = sorted(operand_counts.items(), key=lambda item: item[0].lower())
        total_rows = max(len(operators), len(operands))

        for index in range(total_rows):
            operator, operator_count = operators[index] if index < len(operators) else ("", "")
            operand, operand_count = operands[index] if index < len(operands) else ("", "")
            self.table.insert(
                "",
                tk.END,
                values=(
                    index + 1 if index < len(operators) else "",
                    operator,
                    operator_count,
                    index + 1 if index < len(operands) else "",
                    operand,
                    operand_count,
                ),
            )

        self.table.insert(
            "",
            tk.END,
            values=(f"η₁ = {eta1}", "", f"N₁ = {n1}", f"η₂ = {eta2}", "", f"N₂ = {n2}"),
        )

        self.summary.configure(
            text=(
                f"Словарь программы: η = η₁ + η₂ = {eta1} + {eta2} = {vocabulary}.    "
                f"Длина программы: N = N₁ + N₂ = {n1} + {n2} = {length}.    "
                f"Объём программы: V = N × log₂(η) = {volume:.2f}."
            )
        )

    def clear(self):
        self.code_text.delete("1.0", tk.END)
        for row in self.table.get_children():
            self.table.delete(row)
        self.summary.configure(text="Введите Kotlin-код и нажмите «Рассчитать метрики».")


if __name__ == "__main__":
    HalsteadApp().mainloop()
