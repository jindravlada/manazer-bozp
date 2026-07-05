import unittest

from core.dashboard.task_links import task_id_from_link, task_link


class DashboardTaskLinksTests(unittest.TestCase):
    def test_task_link_contains_task_id(self) -> None:
        link = task_link(42, "Kontrola hasicích přístrojů")
        self.assertIn('href="task:42"', link)
        self.assertIn("Kontrola hasicích přístrojů", link)

    def test_task_link_escapes_html(self) -> None:
        link = task_link(1, 'A & B <script>"x"')
        self.assertIn("A &amp; B &lt;script&gt;&quot;x&quot;", link)

    def test_task_id_from_link(self) -> None:
        self.assertEqual(task_id_from_link("task:17"), 17)
        self.assertIsNone(task_id_from_link("https://example.com"))
        self.assertIsNone(task_id_from_link("task:not-a-number"))


if __name__ == "__main__":
    unittest.main()
