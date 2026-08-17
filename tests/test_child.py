import unittest

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.config import ChildConfig
from child.curriculum import load_stage
from child.model import Child


class ChildTests(unittest.TestCase):
    def test_russian_roundtrip(self) -> None:
        text = "Мама ест яблоко."
        tensor = text_to_bytes(text)
        self.assertEqual(bytes_to_text(tensor), text)
        self.assertEqual(tensor.dtype, torch.long)
        self.assertLess(int(tensor.max()), 256)

    def test_forward_and_loss_shape(self) -> None:
        config = ChildConfig(block_size=32, n_layer=2, n_head=2, n_embd=32)
        model = Child(config)
        idx = torch.randint(0, 256, (4, 32))
        targets = torch.randint(0, 256, (4, 32))
        logits, loss = model(idx, targets)
        self.assertEqual(logits.shape, (4, 32, 256))
        self.assertIsNotNone(loss)
        assert loss is not None
        self.assertTrue(torch.isfinite(loss))

    def test_generate_grows_sequence(self) -> None:
        config = ChildConfig(block_size=32, n_layer=2, n_head=2, n_embd=32)
        model = Child(config)
        idx = text_to_bytes("Привет").unsqueeze(0)
        out = model.generate(idx, max_new_bytes=8, temperature=1.0, top_k=50)
        self.assertEqual(out.shape[1], idx.shape[1] + 8)

    def test_russian_stage_is_long_enough(self) -> None:
        text = load_stage("russian_yasli")
        data = text_to_bytes(text)
        self.assertGreater(data.numel(), ChildConfig().block_size * 4)
        self.assertIn("Мама", text)
        self.assertIn("Привет", text)


if __name__ == "__main__":
    unittest.main()
