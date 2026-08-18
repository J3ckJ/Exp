from __future__ import annotations

from child.talk import format_pair

# Python as another language of bytes. Tiny programs a child can hear often.

_PYTHON_SNIPPETS = """
print("hello")
print("mama")
print("papa")
x = 1
y = 2
print(x)
print(y)
name = "Child"
print(name)
if x > 0:
    print("yes")
if y < 0:
    print("no")
for i in range(3):
    print(i)

def hi():
    print("hi")

hi()

def add(a, b):
    return a + b

print(add(1, 2))
"""

_PY_TALK: tuple[tuple[str, str], ...] = (
    ("What is Python?", "Python is a language."),
    ("What is print?", "print writes text."),
    ("Write hello", 'print("hello")'),
    ("How to print mama?", 'print("mama")'),
    ("What is a variable?", "A name for a value. x = 1"),
    ("What is if?", "if checks a condition."),
    ("What is for?", "for repeats."),
    ("What is a function?", "def makes a function."),
    ("Do you code?", "I am learning Python."),
    ("Show print", 'print("hello")'),
    ("Что такое Python?", "Python is a language."),
    ("Как написать привет?", 'print("hello")'),
    ("Что делает print?", "print writes text."),
    ("What is GitHub?", "GitHub is where code lives."),
    ("Что такое GitHub?", "GitHub is where code lives."),
    ("Run print hello", 'print("hello")'),
    ("Выполни print", 'print("hello")'),
)


def python_body() -> str:
    talk = "".join(format_pair(user, child) for user, child in _PY_TALK)
    code = _PYTHON_SNIPPETS.strip() + "\n"
    return (code * 10) + (talk * 8)
