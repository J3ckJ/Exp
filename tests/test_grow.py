import unittest

from child.config import age_name, next_age, preschooler_config, schoolkid_config, toddler_config
from child.grow import should_grow, wants_grow


class GrowTests(unittest.TestCase):
    def test_ladder(self) -> None:
        self.assertEqual(age_name(toddler_config()), "toddler")
        self.assertEqual(age_name(preschooler_config()), "preschooler")
        self.assertEqual(age_name(schoolkid_config()), "schoolkid")
        self.assertEqual(next_age("preschooler"), "schoolkid")
        self.assertIsNone(next_age("schoolkid"))

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
        ok, reason = should_grow("schoolkid", loss=0.9, new_bytes=9000, allow=True, force=True)
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


if __name__ == "__main__":
    unittest.main()
