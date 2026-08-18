import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from child.agent import route_tools
from child.curriculum import load_stage
from child.memory import retrieve
from child.morning import MORNING_PROMPTS
from child.night import fit_steps, minutes_left, still_night
from child.tools import first_fact, moscow_date, moscow_now, safe_calc
from child.web import host_allowed
from child.wish import parse_wish


class JarvisTests(unittest.TestCase):
    def test_time_tool(self) -> None:
        text = route_tools("Который час?")
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Москве", text)
        self.assertRegex(moscow_now(), r"\d{2}:\d{2}")

    def test_calc_tool(self) -> None:
        self.assertEqual(route_tools("сколько будет 2+2"), "4")
        self.assertEqual(safe_calc("10/2"), "5")
        self.assertEqual(safe_calc("__import__('os')"), "")

    def test_plain_hello_is_speech(self) -> None:
        self.assertIsNone(route_tools("Привет"))
        self.assertIsNone(route_tools("Hello"))

    def test_retrieve_finds_brain(self) -> None:
        hits = retrieve("Мама яблоко")
        self.assertTrue(any("яблоко" in line.casefold() for line in hits))

    def test_world_school_has_moscow(self) -> None:
        text = load_stage("world_school")
        self.assertIn("Столица России — Москва.", text)
        self.assertIn("Мама читает книгу.", text)
        self.assertIn("Hello.", text)
        self.assertGreaterEqual(len(MORNING_PROMPTS), 8)

    def test_status_tool(self) -> None:
        text = route_tools("сколько шагов")
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("шагов", text)

    def test_wiki_host_still_allowed(self) -> None:
        self.assertTrue(host_allowed("https://ru.wikipedia.org/api/rest_v1/page/summary/Москва"))

    def test_date_tool(self) -> None:
        text = route_tools("какое сегодня число")
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Сегодня", text)
        self.assertRegex(moscow_date(), r"(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)")

    def test_know_tool_reads_brain(self) -> None:
        text = route_tools("что ты знаешь про маму")
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("мама", text.casefold())

    def test_first_fact_keeps_long_useful_sentence(self) -> None:
        extract = (
            "Москва — столица России, город федерального значения, "
            "административный центр Центрального федерального округа "
            "и центр Московской области, в состав которой не входит. "
            "Центр Московской городской агломерации."
        )
        fact = first_fact(extract, "Москва")
        self.assertIn("Москва", fact)
        self.assertIn("столица", fact.casefold())

    def test_world_wish(self) -> None:
        wish = parse_wish("поучи мир в интернете")
        self.assertEqual(wish.topic, "world")
        self.assertTrue(wish.use_web)

    def test_night_clock_before_deadline(self) -> None:
        now = datetime(2026, 8, 18, 3, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        self.assertTrue(still_night(now))
        self.assertGreater(minutes_left(now), 200)
        self.assertGreater(fit_steps(1000, now), 200)

    def test_night_clock_after_deadline(self) -> None:
        now = datetime(2026, 8, 18, 7, 21, tzinfo=ZoneInfo("Europe/Moscow"))
        self.assertFalse(still_night(now))
        self.assertEqual(fit_steps(1000, now), 0)


if __name__ == "__main__":
    unittest.main()
