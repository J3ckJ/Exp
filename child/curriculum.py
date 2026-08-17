from __future__ import annotations

from typing import Callable, Sequence

# First school: simple Russian a child can hear many times.
# Yasli kept as the newborn lesson. Later stages overwrite bad
# cartesian habits: a teacher does not say "читает яблоко".


_PEOPLE = (
    "Мама",
    "Папа",
    "Бабушка",
    "Дедушка",
    "Мальчик",
    "Девочка",
    "Учитель",
    "Друг",
)

_RU_SUBJECTS = _PEOPLE + ("Кошка", "Собака")

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

# Living collocations only. Food is eaten, books are read, doors open.
_FRAMES: tuple[tuple[Sequence[str], Sequence[str], Sequence[str]], ...] = (
    (_PEOPLE, ("ест",), ("яблоко", "хлеб", "кашу", "суп")),
    (_PEOPLE, ("пьёт",), ("воду", "молоко", "чай")),
    (_PEOPLE, ("читает",), ("книгу", "письмо")),
    (_PEOPLE, ("пишет",), ("письмо",)),
    (
        _PEOPLE,
        ("видит",),
        ("дом", "окно", "стол", "маму", "папу", "кошку", "солнце"),
    ),
    (_PEOPLE, ("рисует",), ("дом", "солнце", "кошку")),
    (_PEOPLE, ("моет",), ("окно", "стол", "руки")),
    (_PEOPLE, ("открывает", "закрывает"), ("окно", "дверь", "книгу")),
)

_ANIMAL_LINES = (
    "Кошка ест кашу.",
    "Кошка пьёт молоко.",
    "Кошка видит собаку.",
    "Кошка сидит дома.",
    "Кошка идёт в сад.",
    "Собака сидит дома.",
    "Собака идёт на улице.",
    "Собака видит кошку.",
    "Собака любит дом.",
)

_DIALOGUES = (
    "Привет.\nПривет. Как дела?\nХорошо. Спасибо.",
    "Доброе утро.\nДоброе утро. Мы дома.",
    "Спокойной ночи.\nСпокойной ночи. Ночь тёмная.",
    "Кто это?\nЭто мама.",
    "Кто это?\nЭто папа.",
    "Что это?\nЭто дом.",
    "Что это?\nЭто книга.",
    "Где мама?\nМама дома.",
    "Где папа?\nПапа в саду.",
    "Что делает мама?\nМама читает книгу.",
    "Что делает папа?\nПапа пьёт чай.",
    "Что ест мама?\nМама ест яблоко.",
    "Что пьёт папа?\nПапа пьёт чай.",
)

_STORIES = (
    "Мама дома. Мама читает книгу.",
    "Папа дома. Папа пьёт чай.",
    "Мама ест яблоко. Папа ест хлеб.",
    "Девочка рисует солнце. Мальчик читает книгу.",
    "Учитель видит окно. Учитель открывает окно.",
    "Бабушка сидит за столом. Дедушка идёт в сад.",
    "Кошка пьёт молоко. Собака сидит дома.",
    "Я здесь. Я учусь говорить.",
    "День светлый. Солнце жёлтое.",
    "Ночь тёмная. Спокойной ночи.",
    "Мама любит папу. Папа любит маму.",
    "Ребёнок слушает речь. Слова идут одно за другим.",
)

_GOLD = (
    "Привет.",
    "Здравствуй.",
    "Доброе утро.",
    "Мама ест яблоко.",
    "Папа пьёт чай.",
    "Мама читает книгу.",
    "Папа пишет письмо.",
    "Мама видит дом.",
    "Мама любит папу.",
    "Папа любит маму.",
    "Мама моет окно.",
    "Папа открывает дверь.",
    "Мама закрывает окно.",
    "Кошка пьёт молоко.",
    "Собака сидит дома.",
    "Я здесь.",
    "Это мама.",
    "Это папа.",
    "Меня зовут Ребёнок.",
    "Я учусь говорить.",
    "Кто это? Это мама.",
    "Что делает мама? Мама читает книгу.",
    "Где мама? Мама дома.",
)


def _join(lines: Sequence[str], repeats: int) -> str:
    text = "\n".join(lines)
    return (text + "\n") * repeats


def _frame_lines() -> list[str]:
    lines: list[str] = []
    for subjects, verbs, objects in _FRAMES:
        for subject in subjects:
            for verb in verbs:
                for obj in objects:
                    lines.append(f"{subject} {verb} {obj}.")
    for subject in _PEOPLE:
        if subject != "Мама":
            lines.append(f"{subject} любит маму.")
        if subject != "Папа":
            lines.append(f"{subject} любит папу.")
        lines.append(f"{subject} любит дом.")
        lines.append(f"{subject} любит кошку.")
        for place in _RU_PLACES:
            lines.append(f"{subject} сидит {place}.")
            lines.append(f"{subject} идёт {place}.")
    return lines


def build_russian_yasli() -> str:
    lines: list[str] = list(_RU_GREETINGS) + list(_RU_FACTS)
    for subject in _RU_SUBJECTS:
        for verb in _RU_VERBS:
            for obj in _RU_OBJECTS:
                lines.append(f"{subject} {verb} {obj}.")
        for place in _RU_PLACES:
            lines.append(f"{subject} сидит {place}.")
            lines.append(f"{subject} идёт {place}.")
    return _join(lines, 3)


def build_russian_core() -> str:
    """Drill the sentences a child should say without thinking."""
    lines = list(_RU_GREETINGS) + list(_RU_FACTS) + list(_GOLD)
    return _join(lines, 12)


def build_russian_school() -> str:
    """A full Russian day: living frames, talk, stories, old greetings."""
    lines: list[str] = []
    lines.extend(_RU_GREETINGS)
    lines.extend(_RU_FACTS)
    lines.extend(_frame_lines())
    lines.extend(_ANIMAL_LINES)
    lines.extend(_DIALOGUES)
    lines.extend(_STORIES)
    lines.extend(_GOLD)
    return _join(lines, 4)


def build_russian_recitation() -> str:
    """Quiet recitation at the end of the day. Gold only, many times."""
    lines = list(_GOLD) + list(_DIALOGUES) + list(_STORIES)
    return _join(lines, 16)


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
    "russian_core": build_russian_core,
    "russian_school": build_russian_school,
    "russian_recitation": build_russian_recitation,
    "english_placeholder": build_english_placeholder,
    "python_placeholder": build_python_placeholder,
}


def gold_lines() -> tuple[str, ...]:
    return _GOLD


def load_stage(name: str) -> str:
    builder = CURRICULUM.get(name)
    if builder is None:
        known = ", ".join(sorted(CURRICULUM))
        raise KeyError(f"Unknown stage {name!r}. Known: {known}")
    return builder()
