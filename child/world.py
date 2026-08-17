from __future__ import annotations

from child.talk import format_pair

_WORLD_FACTS = (
    "Столица России — Москва.",
    "Столица Англии — Лондон.",
    "Земля — планета.",
    "Солнце — звезда.",
    "Вода мокрая.",
    "Огонь горячий.",
    "Два плюс два — четыре.",
    "Один, два, три, четыре, пять.",
    "Понедельник, вторник, среда.",
    "Москва в России.",
    "London is the capital of England.",
    "Moscow is the capital of Russia.",
    "The Earth is a planet.",
    "The Sun is a star.",
    "Two plus two is four.",
)

_WORLD_TALK: tuple[tuple[str, str], ...] = (
    ("Какая столица России?", "Москва."),
    ("Столица России?", "Москва."),
    ("What is the capital of Russia?", "Moscow."),
    ("What is the capital of England?", "London."),
    ("Что такое Земля?", "Земля — планета."),
    ("What is the Earth?", "The Earth is a planet."),
    ("Что такое Солнце?", "Солнце — звезда."),
    ("Сколько будет два плюс два?", "Четыре."),
    ("What is two plus two?", "Four."),
    ("Который час?", "Сейчас скажу время."),
    ("Запомни", "Запомнил."),
    ("Узнай", "Сейчас посмотрю."),
)


def world_body() -> str:
    facts = "\n".join(_WORLD_FACTS) + "\n"
    talk = "".join(format_pair(user, child) for user, child in _WORLD_TALK)
    return (facts * 8) + (talk * 8)
