from __future__ import annotations

import ast
import operator

from child.memory import load_brain_entries

MAX_STATEMENTS = 8
MAX_OUTPUT = 400
MAX_RANGE = 12
ALLOWED_FUNCS = {"print", "range", "len", "int", "str", "abs", "min", "max"}
RUN_MARKERS = (
    "выполни",
    "запусти",
    "исполни",
    "run python",
    "run:",
    "run ",
)
READ_MARKERS = (
    "прочитай тетрадь",
    "покажи тетрадь",
    "открой тетрадь",
    "что в тетради",
    "read the notebook",
    "show notebook",
)
HANDS_HELP_MARKERS = (
    "что умеют руки",
    "какие руки",
    "что делают руки",
    "show hands",
    "list tools",
)
HANDS_HELP = (
    "Руки: время, дата, запомнить, тетрадь, интернет, счёт, простой Python, "
    "учиться ртом («поучи»), вырасти, сам искать («изучи») и решать, чему учиться дальше. "
    "Страницы продуктов в веса не идут."
)

_UNSAFE = (
    ast.Import,
    ast.ImportFrom,
    ast.Attribute,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.Lambda,
    ast.While,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.Delete,
    ast.Raise,
    ast.Try,
)
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_UNOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_CMP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def looks_like_code(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith(("print(", "for ", "if ", "x =", "name =", "y =")):
        return True
    if "print(" in stripped and any(ch in stripped for ch in (";", "\n", "=")):
        return True
    return False


def extract_code(user: str) -> str:
    low = user.casefold()
    for marker in RUN_MARKERS:
        idx = low.find(marker)
        if idx >= 0:
            return user[idx + len(marker) :].strip(" :,-")
    if looks_like_code(user):
        return user.strip()
    return ""


def safe_python(code: str) -> str:
    code = code.strip()
    if not code:
        return "Какой код?"
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        return "Не понял код."
    for node in ast.walk(tree):
        if isinstance(node, _UNSAFE):
            return "Я ещё маленький. Только простой print, числа и for."
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            return "Я ещё маленький. Только простой print, числа и for."
        if isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Name) or func.id not in ALLOWED_FUNCS:
                return "Я ещё маленький. Только простой print, числа и for."
    try:
        out = _Runner().run(tree)
    except (ValueError, TypeError, ZeroDivisionError, KeyError, RecursionError):
        return "Я ещё маленький. Только простой print, числа и for."
    if not out:
        return "(пусто)"
    return out[:MAX_OUTPUT]


class _Runner:
    def __init__(self) -> None:
        self.env: dict[str, object] = {}
        self.lines: list[str] = []

    def run(self, tree: ast.Module) -> str:
        if len(tree.body) > MAX_STATEMENTS:
            raise ValueError("too long")
        for stmt in tree.body:
            self.visit_stmt(stmt)
        return "\n".join(self.lines)

    def visit_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise ValueError("unsafe")
            name = stmt.targets[0].id
            if name.startswith("_") or name in ALLOWED_FUNCS:
                raise ValueError("unsafe")
            self.env[name] = self.eval(stmt.value)
            return
        if isinstance(stmt, ast.Expr):
            self.eval(stmt.value)
            return
        if isinstance(stmt, ast.If):
            if self.eval(stmt.test):
                for inner in stmt.body:
                    self.visit_stmt(inner)
            else:
                for inner in stmt.orelse:
                    self.visit_stmt(inner)
            return
        if isinstance(stmt, ast.For):
            if not isinstance(stmt.target, ast.Name):
                raise ValueError("unsafe")
            iterable = self.eval(stmt.iter)
            if not isinstance(iterable, (list, tuple, range)):
                raise ValueError("unsafe")
            items = list(iterable)
            if len(items) > MAX_RANGE:
                raise ValueError("unsafe")
            for item in items:
                self.env[stmt.target.id] = item
                for inner in stmt.body:
                    self.visit_stmt(inner)
            return
        raise ValueError("unsafe")

    def eval(self, node: ast.AST) -> object:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in self.env:
                raise KeyError(node.id)
            return self.env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left = self.eval(node.left)
            right = self.eval(node.right)
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise ValueError("unsafe")
            return _BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNOPS:
            value = self.eval(node.operand)
            if not isinstance(value, (int, float)):
                raise ValueError("unsafe")
            return _UNOPS[type(node.op)](value)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left = self.eval(node.left)
            right = self.eval(node.comparators[0])
            op = node.ops[0]
            if type(op) not in _CMP:
                raise ValueError("unsafe")
            return _CMP[type(op)](left, right)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("unsafe")
            args = [self.eval(arg) for arg in node.args]
            return self.call(node.func.id, args)
        if isinstance(node, ast.List):
            if len(node.elts) > MAX_RANGE:
                raise ValueError("unsafe")
            return [self.eval(elt) for elt in node.elts]
        raise ValueError("unsafe")

    def call(self, name: str, args: list[object]) -> object:
        if name == "print":
            self.lines.append(" ".join(str(arg) for arg in args))
            return None
        if name == "range":
            if not args or len(args) > 3:
                raise ValueError("unsafe")
            nums: list[int] = []
            for arg in args:
                if not isinstance(arg, int):
                    raise ValueError("unsafe")
                nums.append(arg)
            result = range(*nums)
            if len(result) > MAX_RANGE:
                raise ValueError("unsafe")
            return result
        if name == "len":
            if len(args) != 1:
                raise ValueError("unsafe")
            value = args[0]
            if not isinstance(value, (str, list, tuple, range)):
                raise ValueError("unsafe")
            return len(value)
        if name == "int":
            if len(args) != 1:
                raise ValueError("unsafe")
            return int(args[0])  # type: ignore[arg-type]
        if name == "str":
            if len(args) != 1:
                raise ValueError("unsafe")
            return str(args[0])
        if name == "abs":
            if len(args) != 1 or not isinstance(args[0], (int, float)):
                raise ValueError("unsafe")
            return abs(args[0])
        if name in {"min", "max"}:
            if not args:
                raise ValueError("unsafe")
            return min(args) if name == "min" else max(args)
        raise ValueError("unsafe")


def read_notebook(limit: int = 10) -> str:
    entries = load_brain_entries()
    remembered = [line for section, line in entries if section == "запомнил"]
    world = [line for section, line in entries if section == "мир"]
    picked = remembered[-6:] + world[:6]
    if not picked:
        picked = [line for _section, line in entries[:limit]]
    if not picked:
        return "Тетрадь пустая."
    return " ".join(picked[:limit])[:500]


def wants_notebook(user: str) -> bool:
    low = user.casefold()
    return any(marker in low for marker in READ_MARKERS)


def wants_hands_help(user: str) -> bool:
    low = user.casefold()
    return any(marker in low for marker in HANDS_HELP_MARKERS)
