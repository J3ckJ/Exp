import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from child.gather import gather_all
from child.ingest import iter_text_files, mix_study, split_practice_lines
from child.learn import brain_sentences, load_brain
from child.wish import parse_wish


class SelfLearnTests(unittest.TestCase):
    def test_split_keeps_short_russian_sentences(self) -> None:
        text = "Я сам читаю.\n\nМама рядом. Theme\n3.1.\nЭто слишком длинная строка которая должна исчезнуть если она правда очень очень очень очень очень очень длинная для рта ребёнка.\n# заголовок\nДа."
        lines = split_practice_lines(text)
        self.assertIn("Я сам читаю.", lines)
        self.assertIn("Мама рядом.", lines)
        self.assertNotIn("# заголовок", lines)
        self.assertNotIn("Theme", lines)
        self.assertNotIn("3.1.", lines)
        self.assertNotIn("Navigation", split_practice_lines("Navigation\nShow source\nМама рядом."))

    def test_mix_repeats_old_and_new(self) -> None:
        mixed = mix_study(("старое\n", 2), ("новое\n", 3))
        self.assertEqual(mixed.count("старое"), 2)
        self.assertEqual(mixed.count("новое"), 3)

    def test_gather_sees_extra_without_web(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            book = root / "book.txt"
            book.write_text("Привет.\n", encoding="utf-8")
            paths = gather_all(parse_wish("учиться"), [book], [], use_web=False)
            self.assertIn(book, paths)
            files = iter_text_files([book])
            self.assertEqual(files, [book])

    def test_brain_skips_headings(self) -> None:
        text = load_brain()
        lines = brain_sentences(text)
        self.assertIn("Мама читает книгу.", lines)
        self.assertTrue(all(not line.startswith("#") for line in lines))


if __name__ == "__main__":
    unittest.main()
