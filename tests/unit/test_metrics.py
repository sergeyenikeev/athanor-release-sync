"""Unit-тесты калькулятора метрик: P/R/F1, сопоставление, перцентили."""
import unittest

from tests.run_basket import _match, _prf
from tests.score import _percentile


class TestMetrics(unittest.TestCase):
    def test_prf_perfect(self):
        p, r, f1 = _prf(5, 0, 0)
        self.assertEqual((p, r, f1), (1.0, 1.0, 1.0))

    def test_prf_empty(self):
        p, r, f1 = _prf(0, 0, 0)
        self.assertEqual(p, 1.0)  # нет ни ожидаемых, ни выданных — точность 1.0 по соглашению

    def test_prf_half(self):
        p, r, f1 = _prf(4, 1, 1)
        self.assertAlmostEqual(p, 0.8)
        self.assertAlmostEqual(r, 0.8)
        self.assertAlmostEqual(f1, 0.8)

    def test_match_strict(self):
        actual = [{"action": "деплой", "owner": "SRE", "due": "2026-07-03", "source": "OPS-77"}]
        expected = [{"action": "Деплой ", "owner": " sre", "due": "2026-07-03", "source": "OPS-77"}]
        tp, fp, fn = _match(actual, expected, ["action", "owner", "due", "source"])
        self.assertEqual((tp, fp, fn), (1, 0, 0))  # нормализация регистра/пробелов

    def test_match_fp_fn(self):
        actual = [{"action": "x", "owner": "A", "due": "d", "source": "s"},
                  {"action": "лишнее", "owner": "B", "due": "d2", "source": "s2"}]
        expected = [{"action": "x", "owner": "A", "due": "d", "source": "s"},
                    {"action": "missed", "owner": "C", "due": "d3", "source": "s3"}]
        tp, fp, fn = _match(actual, expected, ["action", "owner", "due", "source"])
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 1)

    def test_percentile(self):
        vals = sorted([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        self.assertAlmostEqual(_percentile(vals, 0.5), 0.55, places=1)
        self.assertGreaterEqual(_percentile(vals, 0.95), 0.9)
        self.assertEqual(_percentile([], 0.5), 0.0)
        self.assertEqual(_percentile([0.42], 0.5), 0.42)


if __name__ == "__main__":
    unittest.main()
