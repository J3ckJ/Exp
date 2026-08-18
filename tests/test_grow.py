import unittest

import torch

from child.config import (
    ChildConfig,
    age_name,
    next_age,
    preschooler_config,
    schoolkid_config,
    teen_config,
    toddler_config,
)
from child.grow import should_grow, wants_grow
from child.model import Child
from child.transplant import transplant


class GrowTests(unittest.TestCase):
    def test_ladder(self) -> None:
        self.assertEqual(age_name(toddler_config()), "toddler")
        self.assertEqual(age_name(preschooler_config()), "preschooler")
        self.assertEqual(age_name(schoolkid_config()), "schoolkid")
        self.assertEqual(age_name(teen_config()), "teen")
        self.assertEqual(next_age("preschooler"), "schoolkid")
        self.assertEqual(next_age("schoolkid"), "teen")
        self.assertIsNone(next_age("teen"))

    def test_easy_lesson_does_not_grow(self) -> None:
        ok, reason = should_grow("preschooler", loss=0.08, new_bytes=9000, allow=True, force=False)
        self.assertFalse(ok)
        self.assertIn("chewed", reason)

    def test_hard_lesson_grows(self) -> None:
        ok, reason = should_grow("preschooler", loss=0.72, new_bytes=9000, allow=True, force=False)
        self.assertTrue(ok)
        self.assertIn("schoolkid", reason)

    def test_tiny_page_does_not_grow(self) -> None:
        ok, _reason = should_grow("preschooler", loss=0.9, new_bytes=40, allow=True, force=False)
        self.assertFalse(ok)

    def test_top_of_ladder(self) -> None:
        ok, reason = should_grow("teen", loss=0.9, new_bytes=9000, allow=True, force=True)
        self.assertFalse(ok)
        self.assertIn("largest", reason)

    def test_force_even_if_easy(self) -> None:
        ok, _reason = should_grow("preschooler", loss=0.04, new_bytes=10, allow=False, force=True)
        self.assertTrue(ok)

    def test_wish_to_grow(self) -> None:
        self.assertTrue(wants_grow("вырасти"))
        self.assertTrue(wants_grow("набери параметры сам"))
        self.assertFalse(wants_grow("Привет"))
        self.assertFalse(wants_grow("поучи python"))

    def test_transplant_keeps_the_old_song(self) -> None:
        torch.manual_seed(0)
        old = Child(
            ChildConfig(block_size=16, n_layer=2, n_head=2, n_embd=16, dropout=0.0)
        )
        old.eval()
        young = transplant(
            old,
            ChildConfig(block_size=32, n_layer=3, n_head=2, n_embd=16, dropout=0.0),
        )
        young.eval()
        idx = torch.randint(0, 256, (2, 16))
        left, _ = old(idx)
        right, _ = young(idx)
        self.assertTrue(torch.allclose(left, right, atol=1e-5, rtol=1e-4))
        self.assertGreater(young.count_parameters(), old.count_parameters())
        self.assertEqual(young.config.block_size, 32)
        self.assertEqual(young.config.n_layer, 3)

    def test_grow_model_schoolkid_to_teen(self) -> None:
        from child.grow import grow_model

        old = Child(schoolkid_config())
        young, current, nxt = grow_model(old)
        self.assertEqual(current, "schoolkid")
        self.assertEqual(nxt, "teen")
        self.assertEqual(young.config.block_size, 512)
        self.assertEqual(young.config.n_layer, 10)
        self.assertGreater(young.count_parameters(), old.count_parameters())


if __name__ == "__main__":
    unittest.main()
