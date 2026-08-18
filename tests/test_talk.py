import unittest

from child.bytes_io import text_to_bytes
from child.config import ChildConfig
from child.curriculum import load_stage
from child.model import Child
from child.talk import clean_reply, format_pair, format_prompt


class TalkTests(unittest.TestCase):
    def test_talk_stage_is_turns_not_mash(self) -> None:
        text = load_stage("russian_talk")
        self.assertIn("Ты: Привет\nЯ: Привет.", text)
        self.assertIn("Ты: Кто ты?", text)
        self.assertIn("Меня зовут Тима.", text)
        self.assertIn("Мама читает книгу.", text)
        self.assertNotIn("Мама читает яблоко.", text)

    def test_prompt_fits_tiny_mouth(self) -> None:
        prompt = format_prompt("Привет", [], block_size=96)
        self.assertTrue(prompt.endswith("Я: "))
        self.assertLessEqual(len(prompt.encode("utf-8")), 96)
        longer = format_prompt(
            "Как дела?",
            [("Привет", "Привет. Как дела?")],
            block_size=96,
        )
        self.assertLessEqual(len(longer.encode("utf-8")), 96)

    def test_clean_reply_cuts_at_newline_and_user_tag(self) -> None:
        self.assertEqual(clean_reply("Привет.\nТы: Как дела?"), "Привет.")
        self.assertEqual(clean_reply("Хорошо. Ты: нет"), "Хорошо.")

    def test_generate_accepts_stop_bytes(self) -> None:
        config = ChildConfig(block_size=32, n_layer=2, n_head=2, n_embd=32)
        model = Child(config)
        idx = text_to_bytes("Привет").unsqueeze(0)
        out = model.generate(idx, max_new_bytes=8, stop_bytes=(10,))
        self.assertGreaterEqual(out.shape[1], idx.shape[1])
        self.assertLessEqual(out.shape[1], idx.shape[1] + 8)

    def test_preschooler_is_still_a_child(self) -> None:
        from child.config import preschooler_config

        model = Child(preschooler_config())
        n_params = model.count_parameters()
        self.assertGreater(n_params, 2_000_000)
        self.assertLess(n_params, 4_000_000)
        self.assertEqual(model.config.block_size, 192)

    def test_power_stage_teaches_not_knowing(self) -> None:
        text = load_stage("russian_power")
        self.assertIn("Ты: Почему небо голубое?", text)
        self.assertIn("Я ещё маленький. Я не знаю.", text)
        self.assertIn("Ты: Приветик", text)
        self.assertIn("Мама читает книгу.", text)

    def test_format_pair_shape(self) -> None:
        self.assertEqual(format_pair("Привет", "Привет."), "Ты: Привет\nЯ: Привет.\n")


if __name__ == "__main__":
    unittest.main()
