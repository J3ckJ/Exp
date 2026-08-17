import unittest

from child.curriculum import load_stage
from child.web import host_allowed
from child.wish import is_learn_command, parse_wish


class NightTests(unittest.TestCase):
    def test_wish_detects_python_and_web(self) -> None:
        wish = parse_wish("Поучи пока python на гитхабе и в интернете")
        self.assertEqual(wish.topic, "python")
        self.assertTrue(wish.use_web)
        self.assertTrue(is_learn_command(wish.raw))

    def test_wish_detects_english(self) -> None:
        wish = parse_wish("learn english please")
        self.assertEqual(wish.topic, "english")
        self.assertTrue(is_learn_command("learn english please"))

    def test_plain_hello_is_not_a_study_order(self) -> None:
        self.assertFalse(is_learn_command("Привет"))
        self.assertFalse(is_learn_command("How are you?"))

    def test_web_whitelist(self) -> None:
        self.assertTrue(host_allowed("https://docs.python.org/3/tutorial/introduction.html"))
        self.assertTrue(host_allowed("https://en.wikipedia.org/api/rest_v1/page/summary/Hello"))
        self.assertFalse(host_allowed("https://evil.example/steal"))

    def test_english_school_keeps_russian(self) -> None:
        text = load_stage("english_school")
        self.assertIn("Hello.", text)
        self.assertIn("Mama eats an apple.", text)
        self.assertIn("Мама ест яблоко.", text)
        self.assertIn("Ты: Hello", text)

    def test_python_school_has_print_and_memory(self) -> None:
        text = load_stage("python_school")
        self.assertIn('print("hello")', text)
        self.assertIn("def hi():", text)
        self.assertIn("Мама читает книгу.", text)
        self.assertIn("Ты: What is print?", text)


if __name__ == "__main__":
    unittest.main()
