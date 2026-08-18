import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from child.agent import route_tools
from child.research import is_research_command, mission_query, run_mission
from child.think import already_knows, next_topics
from child.web import host_allowed, query_variants, wiki_search


class ResearchTests(unittest.TestCase):
    def test_research_command_is_not_hello(self) -> None:
        self.assertTrue(is_research_command("изучи как делается ЦРМ в битриксе"))
        self.assertTrue(is_research_command("найди как делают смарт-процесс"))
        self.assertTrue(is_research_command("study how they build CRM"))
        self.assertFalse(is_research_command("Привет"))
        self.assertFalse(is_research_command("что такое Москва"))
        self.assertFalse(is_research_command("поучи python в интернете"))

    def test_mission_query_keeps_the_topic(self) -> None:
        self.assertEqual(
            mission_query("изучи как делается ЦРМ в битриксе").casefold(),
            "црм в битриксе",
        )

    def test_research_wins_over_one_shot_lookup(self) -> None:
        self.assertIsNone(route_tools("изучи как делается ЦРМ в битриксе"))
        self.assertIsNone(route_tools("найди как делают CRM"))
        self.assertIsNone(route_tools("Привет"))

    def test_already_knows_needs_a_title_line(self) -> None:
        with patch(
            "child.think.load_brain_lines",
            return_value=["Битрикс24 — CRM. В смарт-процессах есть PHP."],
        ):
            self.assertFalse(already_knows("PHP"))
        with patch("child.think.load_brain_lines", return_value=["PHP — скриптовый язык."]):
            self.assertTrue(already_knows("PHP"))

    def test_bitrix_page_sends_the_child_to_php(self) -> None:
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics(
                "ЦРМ в битриксе",
                "Битрикс24 — CRM. В смарт-процессах есть блоки PHP кода.",
            )
        topics = [topic for topic, _why in follow]
        self.assertIn("PHP", topics)
        why = " ".join(reason for topic, reason in follow if topic == "PHP")
        self.assertIn("PHP", why)

    def test_plain_hello_does_not_invent_a_lesson(self) -> None:
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("Привет", "Мама читает книгу. Папа пьёт чай.")
        self.assertEqual(follow, [])

    def test_wiki_search_picks_bitrix_over_unrelated(self) -> None:
        with patch(
            "child.web.wiki_search_titles",
            return_value=["CRM", "Битрикс24", "Клиент"],
        ):
            self.assertEqual(wiki_search("црм в битриксе"), "Битрикс24")

    def test_bitrix_phrase_has_search_fallbacks(self) -> None:
        variants = query_variants("ЦРМ в битриксе")
        self.assertIn("Битрикс24", variants)
        self.assertTrue(any(item.casefold() == "битрикс" for item in variants))
        self.assertEqual(wiki_search(""), "")

    def test_wiki_search_host_is_allowed(self) -> None:
        self.assertTrue(
            host_allowed("https://ru.wikipedia.org/w/api.php?action=opensearch&search=PHP")
        )

    def test_mission_reads_then_decides_php(self) -> None:
        def fake_search(query: str) -> str:
            if "php" in query.casefold():
                return "PHP"
            return "Битрикс24"

        def fake_fetch(url: str) -> str:
            if "PHP" in url:
                return (
                    "PHP — скриптовый язык общего назначения, "
                    "часто используется для веб-приложений."
                )
            return (
                "Битрикс24 — российская CRM. "
                "В смарт-процессах администратор может писать блоки PHP."
            )

        with TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            with (
                patch("child.research.wiki_search", side_effect=fake_search),
                patch("child.research.fetch_url", side_effect=fake_fetch),
                patch("child.research.remember", return_value="ok"),
                patch("child.think.load_brain_lines", return_value=[]),
                patch("child.research.PLAN_PATH", plan),
                patch("child.research.urls_for_wish", return_value=[]),
            ):
                report = run_mission("изучи как делается ЦРМ в битриксе")
            self.assertTrue(plan.exists())
            body = plan.read_text(encoding="utf-8")
        self.assertIn("Битрикс24", report)
        self.assertIn("PHP", report)
        self.assertIn("Сам решил", report)
        self.assertIn("PHP", body)
        self.assertIn("Битрикс", body)


if __name__ == "__main__":
    unittest.main()
