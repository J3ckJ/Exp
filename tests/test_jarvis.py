import unittest

from child.agent import route_tools
from child.curriculum import load_stage
from child.memory import retrieve
from child.tools import moscow_now, safe_calc
from child.web import host_allowed


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

    def test_wiki_host_still_allowed(self) -> None:
        self.assertTrue(host_allowed("https://ru.wikipedia.org/api/rest_v1/page/summary/Москва"))


if __name__ == "__main__":
    unittest.main()
