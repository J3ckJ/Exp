from __future__ import annotations

from typing import Callable

# First school: simple Russian sentences a child can hear many times.
# Next ages (english, python) are registered but not taught yet.

_RU_SUBJECTS = (
    "Мама",
    "Папа",
    "Бабушка",
    "Дедушка",
    "Мальчик",
    "Девочка",
    "Кошка",
    "Собака",
    "Учитель",
    "Друг",
)

_RU_VERBS = (
    "ест",
    "пьёт",
    "читает",
    "пишет",
    "видит",
    "любит",
    "рисует",
    "моет",
    "открывает",
    "закрывает",
)

_RU_OBJECTS = (
    "яблоко",
    "воду",
    "книгу",
    "письмо",
    "дом",
    "окно",
    "стол",
    "кошку",
    "солнце",
    "маму",
)

_RU_PLACES = (
    "дома",
    "в саду",
    "в школе",
    "на улице",
    "у окна",
    "за столом",
)

_RU_GREETINGS = (
    "Привет.",
    "Здравствуй.",
    "Доброе утро.",
    "Добрый день.",
    "Добрый вечер.",
    "Спокойной ночи.",
    "Как дела?",
    "Хорошо.",
    "Спасибо.",
    "Пожалуйста.",
    "Да.",
    "Нет.",
)

_RU_FACTS = (
    "Это мама.",
    "Это папа.",
    "Это дом.",
    "Это кот.",
    "Это собака.",
    "Я здесь.",
    "Ты там.",
    "Мы дома.",
    "Небо голубое.",
    "Трава зелёная.",
    "Снег белый.",
    "Солнце жёлтое.",
    "Вода мокрая.",
    "Огонь горячий.",
    "Ночь тёмная.",
    "День светлый.",
    "Один, два, три.",
    "Меня зовут Ребёнок.",
    "Я учусь говорить.",
    "Я слушаю речь.",
    "Слова идут одно за другим.",
    "Сначала имя, потом действие.",
)


def build_russian_yasli() -> str:
    lines: list[str] = list(_RU_GREETINGS) + list(_RU_FACTS)
    for subject in _RU_SUBJECTS:
        for verb in _RU_VERBS:
            for obj in _RU_OBJECTS:
                lines.append(f"{subject} {verb} {obj}.")
        for place in _RU_PLACES:
            lines.append(f"{subject} сидит {place}.")
            lines.append(f"{subject} идёт {place}.")
    # Repeat the core so the tiny child hears the same patterns often.
    text = "\n".join(lines)
    return (text + "\n") * 3


def build_english_placeholder() -> str:
    return (
        "Hello.\n"
        "This stage is not taught yet.\n"
        "The child must learn Russian first.\n"
    )


def build_python_placeholder() -> str:
    return (
        "print('not yet')\n"
        "# First speak. Then English. Then code.\n"
    )


CURRICULUM: dict[str, Callable[[], str]] = {
    "russian_yasli": build_russian_yasli,
    "english_placeholder": build_english_placeholder,
    "python_placeholder": build_python_placeholder,
}


def load_stage(name: str) -> str:
    builder = CURRICULUM.get(name)
    if builder is None:
        known = ", ".join(sorted(CURRICULUM))
        raise KeyError(f"Unknown stage {name!r}. Known: {known}")
    return builder()
