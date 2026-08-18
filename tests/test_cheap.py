import tempfile
import unittest
from pathlib import Path

import torch

from child.config import ChildConfig
from child.identity import INTRO_RU, NAME_RU
from child.lora import attach_lora, count_trainable, merge_lora
from child.model import Child
from child.phrase import PhraseMemory, build_phrases, clear_phrase_cache, load_phrases, save_phrases
from child.talk import format_pair


class PhraseTests(unittest.TestCase):
    def test_longest_suffix_knows_the_next_byte(self) -> None:
        text = format_pair("Кто ты?", INTRO_RU) * 5
        memory = build_phrases([text], lengths=(6, 12, 16))
        prompt = "Ты: Кто ты?\nЯ: ".encode("utf-8")
        found = memory.lookup(prompt)
        self.assertIsNotNone(found)
        counts, match_len, total = found
        assert found is not None
        self.assertGreaterEqual(match_len, 12)
        self.assertGreater(total, 0)
        top = max(counts, key=counts.get)
        self.assertEqual(top, INTRO_RU.encode("utf-8")[0])

    def test_mix_prefers_the_book_on_a_known_turn(self) -> None:
        memory = build_phrases([format_pair("Кто ты?", INTRO_RU) * 20], lengths=(8, 16, 24))
        logits = torch.zeros(256)
        logits[ord("x")] = 4.0
        ctx = "Ты: Кто ты?\nЯ: ".encode("utf-8")
        mixed = memory.mix_probs(logits, ctx, temperature=1.0)
        first = INTRO_RU.encode("utf-8")[0]
        self.assertGreater(float(mixed[first]), float(mixed[ord("x")]))

    def test_save_and_load_roundtrip(self) -> None:
        memory = build_phrases(["HELLO WORLD"], lengths=(6, 8))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.pkl"
            save_phrases(memory, path)
            clear_phrase_cache()
            loaded = load_phrases(path)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.lookup(b"HELLO ")[0], memory.lookup(b"HELLO ")[0])

    def test_merged_model_has_no_lora_modules(self) -> None:
        from child.lora import LoRALinear

        cfg = ChildConfig(block_size=16, n_layer=2, n_head=2, n_embd=16, dropout=0.0)
        model = Child(cfg)
        attach_lora(model, rank=2, last_blocks=1)
        merge_lora(model)
        leftover = [module for module in model.modules() if isinstance(module, LoRALinear)]
        self.assertEqual(leftover, [])


class LoRATests(unittest.TestCase):
    def test_zero_lora_keeps_the_song(self) -> None:
        torch.manual_seed(0)
        cfg = ChildConfig(block_size=16, n_layer=2, n_head=2, n_embd=16, dropout=0.0)
        model = Child(cfg)
        model.eval()
        idx = torch.randint(0, 256, (2, 16))
        before, _ = model(idx)
        attach_lora(model, rank=4, last_blocks=1, alpha=8.0)
        model.eval()
        during, _ = model(idx)
        self.assertTrue(torch.allclose(before, during, atol=1e-5, rtol=1e-4))
        self.assertGreater(count_trainable(model), 0)
        self.assertLess(count_trainable(model), model.count_parameters())
        merge_lora(model)
        model.eval()
        after, _ = model(idx)
        self.assertTrue(torch.allclose(before, after, atol=1e-5, rtol=1e-4))

    def test_name_constant(self) -> None:
        self.assertEqual(NAME_RU, "Тима")
        self.assertIn("Тима", INTRO_RU)


if __name__ == "__main__":
    unittest.main()
