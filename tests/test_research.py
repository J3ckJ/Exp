import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from child.agent import route_tools
from child.research import is_research_command, mission_query, run_mission
from child.think import already_knows, next_topics
from child.web import host_allowed, parse_search_html, query_variants, wiki_search


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

    def test_git_uses_three_tree_not_blog(self) -> None:
        page = (
            "Git uses a three-tree architecture Git Workflow Once Again "
            "Conclusion Designveloper / Blog / Key Programming Languages"
        )
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("как устроен Git", page)
        topics = " ".join(topic for topic, _why in follow).casefold()
        self.assertTrue("tree" in topics or "architecture" in topics)
        self.assertNotIn("blog", topics)
        self.assertNotIn("programming languages", topics)
        self.assertNotIn("clone", topics)

    def test_git_does_not_follow_a_clone_command(self) -> None:
        page = (
            "Git uses a three-tree architecture. "
            "Creating a repo uses git clone command, perfect for new directories."
        )
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("как устроен Git", page)
        topics = " ".join(topic for topic, _why in follow).casefold()
        self.assertIn("tree", topics)
        self.assertNotIn("clone", topics)
        self.assertNotIn("perfect", topics)
        self.assertNotIn("command", topics)

    def test_git_is_not_github(self) -> None:
        page = (
            "GitHub is a proprietary developer platform. "
            "It uses Git to provide distributed version control."
        )
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("как устроен Git", page)
        topics = [topic.casefold() for topic, _why in follow]
        self.assertFalse(any("github" in topic for topic in topics))

    def test_docker_follows_namespaces_not_javascript(self) -> None:
        page = (
            "Docker is a platform that uses Linux namespaces and cgroups "
            "to isolate containers. Also check our REST API and JavaScript course."
        )
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("как устроен Docker", page)
        topics = " ".join(topic for topic, _why in follow).casefold()
        self.assertTrue("namespace" in topics or "cgroup" in topics)
        self.assertNotIn("javascript", topics)
        self.assertNotIn("rest api", topics)

    def test_definition_is_not_enough_for_structure(self) -> None:
        from child.think import deeper_query, needs_deeper

        blurb = (
            "Git is a distributed version control software system that is capable "
            "of managing versions of source code or data. It was originally created "
            "by Linus Torvalds."
        )
        docker = (
            "Docker is a set of products that uses operating system-level "
            "virtualization to deliver software in packages called containers."
        )
        design = (
            "Git maintains a local copy of the entire repository, also known "
            "as the repo, with history and version-tracking abilities."
        )
        self.assertTrue(needs_deeper("как устроен Git", blurb))
        self.assertFalse(needs_deeper("как устроен Docker", docker))
        self.assertTrue(needs_deeper("как устроен Git", design))
        self.assertFalse(
            needs_deeper(
                "как устроен Git",
                "Git stores snapshots in a content-addressable object database of blobs and trees.",
            )
        )
        self.assertFalse(needs_deeper("что такое Git", blurb))
        self.assertEqual(deeper_query("как устроен Git").casefold(), "git internals")

    def test_wiki_trap_skips_generic_architecture_article(self) -> None:
        from child.think import hit_score, wiki_title_fits

        self.assertFalse(wiki_title_fits("Architecture", "как устроен Git"))
        self.assertFalse(wiki_title_fits("Wikipedia", "как устроен Git"))
        self.assertFalse(wiki_title_fits("GitHub", "как устроен Git"))
        self.assertTrue(wiki_title_fits("Git", "как устроен Git"))
        self.assertTrue(wiki_title_fits("Битрикс24", "црм в битриксе"))
        self.assertTrue(wiki_title_fits("PHP", "црм в битриксе"))
        self.assertTrue(
            wiki_title_fits(
                "OS-level virtualization",
                "как устроен Docker",
                "Docker OS-level virtualization",
            )
        )
        self.assertFalse(wiki_title_fits("Internal structure of Earth", "как устроен HTTP"))
        self.assertFalse(wiki_title_fits("HNTB Architecture", "как устроен HTTP"))
        self.assertTrue(wiki_title_fits("HTTP", "как устроен HTTP"))
        git = hit_score(
            "Git",
            "https://en.wikipedia.org/api/rest_v1/page/summary/Git",
            "как устроен Git",
        )
        buildings = hit_score(
            "Architecture",
            "https://en.wikipedia.org/api/rest_v1/page/summary/Architecture",
            "как устроен Git",
        )
        earth = hit_score(
            "Internal structure of Earth",
            "https://en.wikipedia.org/wiki/Internal_structure_of_Earth",
            "как устроен HTTP",
            "HTTP internals",
        )
        http = hit_score(
            "HTTP",
            "https://en.wikipedia.org/wiki/HTTP",
            "как устроен HTTP",
        )
        self.assertGreater(git, buildings)
        self.assertGreater(http, earth)
        blog = hit_score(
            "What Are Git Concepts and Architecture?",
            "https://www.designveloper.com/blog/git-concepts-architecture/",
            "как устроен Git",
        )
        self.assertGreater(git, blog)
        from child.think import search_queries

        queries = " ".join(search_queries("как устроен Docker")).casefold()
        self.assertIn("architecture", queries)
        self.assertIn("docker", queries)

    def test_structure_reads_the_full_wiki_article(self) -> None:
        from child.ingest import is_toc_junk, is_weak_note
        from child.tools import wiki_url

        self.assertIn("titles=Git", wiki_url("Git", "en", full=True))
        self.assertIn("explaintext", wiki_url("Git", "en", full=True))
        self.assertIn("/page/summary/Git", wiki_url("Git", "en"))
        toc = (
            "Git - Plumbing and Porcelain Chapters 1. Getting Started 1.1 About "
            "Version Control 1.2 A Short History of Git 1.3 What is Git? 1.4 "
            "The Command Line 2. Git Basics 2.1 Getting a Git Repository 2.2 "
            "Recording Changes 3. Git Branching 3.1 Branches in a Nutshell"
        )
        self.assertTrue(is_toc_junk(toc))
        self.assertTrue(
            is_weak_note("This is the latest accepted revision , reviewed on 17 August 2026 .", web=True)
        )
        page = (
            "Git - Wikipedia Jump to content From Wikipedia, the free encyclopedia. "
            "Written in Primarily in C, with GUI and programming scripts written in "
            "Shell script, Perl, Tcl and Python. "
            "Git stores content in a content-addressable object database."
        )
        with patch("child.think.load_brain_lines", return_value=[]):
            follow = next_topics("как устроен Git", page)
        topics = " ".join(topic for topic, _why in follow).casefold()
        self.assertNotIn("python", topics)
        self.assertNotIn("shell", topics)
        from child.think import relevant_facts
        from child.web import topic_from_query

        self.assertTrue(is_weak_note("What Are Git Concepts and Architecture?", web=True))
        self.assertTrue(
            is_weak_note(
                '}}"standard":{"wt":""},"AsOf":{"wt":""}} Git',
                web=True,
            )
        )
        self.assertTrue(
            is_weak_note(
                "[ 28 ] Torvalds achieved his performance goals; on 29 April, "
                "the nascent Git was benchmarked recording patches to the Linux kernel.",
                web=True,
            )
        )
        self.assertTrue(
            is_weak_note(
                "Our article offers a concise yet comprehensive overview of Git concepts.",
                web=True,
            )
        )
        self.assertTrue(
            is_weak_note(
                "The Key Components of Git Git Object Types How Git Tracks Content "
                "Staging Index Repositories Git Object Store",
                web=True,
            )
        )
        facts = relevant_facts(
            "Git uses a three-tree architecture Git . It stores snapshots in an object database.",
            "как устроен Git",
        )
        blob = " ".join(facts)
        self.assertTrue("tree" in blob.casefold() or "snapshot" in blob.casefold())
        self.assertNotIn("architecture Git", blob)
        self.assertEqual(topic_from_query("как устроен Git"), "git")
        self.assertEqual(topic_from_query("GitHub Actions"), "github")

    def test_weak_html_is_not_a_note(self) -> None:
        from child.ingest import clean_web_text, is_weak_note

        self.assertTrue(is_weak_note("Courses", web=True))
        self.assertTrue(is_weak_note("Docker для начинающих: что это такое и как пользоваться / Хабр…", web=True))
        cleaned = clean_web_text("Стабильное окружение\\u003C\\u002Fstrong\\u003E")
        self.assertIn("Стабильное окружение", cleaned)
        self.assertNotIn("<", cleaned)

    def test_get_started_loses_to_wikipedia(self) -> None:
        from child.ingest import is_code_junk
        from child.think import hit_score

        wiki = hit_score(
            "Docker",
            "https://en.wikipedia.org/wiki/Docker_(software)",
            "как устроен Docker",
        )
        docs = hit_score(
            "What is Docker?",
            "https://docs.docker.com/get-started/docker-overview/",
            "как устроен Docker",
        )
        self.assertGreater(wiki, docs)
        self.assertTrue(is_code_junk("console.error('Gordon API error:' this.messages.splice"))

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
                patch("child.research.hunt_urls", return_value=[]),
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

    def test_known_php_stays_in_the_plan_but_is_not_fetched(self) -> None:
        def fake_search(query: str) -> str:
            if "php" in query.casefold():
                raise AssertionError("should not hunt PHP again")
            return "Битрикс24"

        def fake_fetch(url: str) -> str:
            if "PHP" in url:
                raise AssertionError("should not fetch PHP again")
            return "Битрикс24 — российская CRM. В смарт-процессах есть блоки PHP."

        with TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            with (
                patch("child.research.hunt_urls", return_value=[]),
                patch("child.research.wiki_search", side_effect=fake_search),
                patch("child.research.fetch_url", side_effect=fake_fetch),
                patch("child.research.remember", return_value="ok"),
                patch("child.think.load_brain_lines", return_value=["PHP — язык."]),
                patch("child.research.PLAN_PATH", plan),
                patch("child.research.urls_for_wish", return_value=[]),
            ):
                report = run_mission("изучи как делается ЦРМ в битриксе")
            body = plan.read_text(encoding="utf-8")
        self.assertIn("Битрикс24", report)
        self.assertIn("уже в тетради", report)
        self.assertIn("PHP", body)

    def test_search_html_unwraps_duckduckgo_results(self) -> None:
        html = (
            '<a class="result__a" href="https://duckduckgo.com/l/?uddg='
            'https%3A%2F%2Fdev.1c-bitrix.ru%2Flearning%2Fcourse%2F">'
            "Смарт-процессы</a>"
            '<a href="https://html.duckduckgo.com/html/">Search</a>'
        )
        hits = parse_search_html(html)
        urls = [url for _title, url in hits]
        self.assertTrue(any("dev.1c-bitrix.ru" in url for url in urls))
        self.assertFalse(any("duckduckgo.com" in url for url in urls))

    def test_mission_reads_a_public_docs_page(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            with (
                patch(
                    "child.research.hunt_urls",
                    return_value=[
                        (
                            "Смарт-процессы",
                            "https://dev.1c-bitrix.ru/learning/smart.php",
                        )
                    ],
                ),
                patch("child.research.wiki_search", return_value=""),
                patch(
                    "child.research.fetch_url",
                    return_value=(
                        "В смарт-процессах Битрикс24 можно добавлять блоки PHP. "
                        "Робот выполняет код на стадии."
                    ),
                ),
                patch("child.research.remember", return_value="ok"),
                patch("child.think.load_brain_lines", return_value=["PHP — язык."]),
                patch("child.research.PLAN_PATH", plan),
                patch("child.research.urls_for_wish", return_value=[]),
            ):
                report = run_mission("изучи как устроены смарт-процессы в битриксе")
        self.assertIn("Смарт-процессы", report)
        self.assertIn("PHP", report)

    def test_wiki_extract_json_is_plain_text(self) -> None:
        from child.web import _json_extract, as_readable_url, topic_from_query

        payload = {
            "query": {
                "pages": {"1": {"title": "Git", "extract": "Git stores snapshots in objects."}}
            }
        }
        self.assertIn("snapshots", _json_extract(payload))
        raw = as_readable_url(
            "https://git-scm.com/book/en/v2/Git-Internals-Git-Objects",
            summary=False,
        )
        self.assertIn("raw.githubusercontent.com", raw)
        self.assertIn("objects.asc", raw)
        self.assertEqual(topic_from_query("как устроен DNS"), "dns")

    def test_expand_follows_the_plan_gap(self) -> None:
        from child.research import gap_from_plan, is_expand_command

        self.assertTrue(is_expand_command("изучи дальше"))
        self.assertTrue(is_expand_command("продолжи"))
        self.assertFalse(is_expand_command("Привет"))
        with TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN.md"
            plan.write_text(
                "# План\n\n## Задание\n\nкак устроен HTTP\n\n"
                "## Сам решил учить дальше\n\n- TCP: потому что запросы идут дальше.\n",
                encoding="utf-8",
            )
            with (
                patch("child.research.PLAN_PATH", plan),
                patch("child.research.knows_deeply", return_value=False),
            ):
                self.assertEqual(gap_from_plan(), "TCP")


if __name__ == "__main__":
    unittest.main()
