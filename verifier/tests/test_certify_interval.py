from __future__ import annotations

import csv
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certify_interval import (  # noqa: E402
    DEFAULT_LINES_PATH,
    DEFAULT_OMATRIX_PATH,
    EPSILON_INTERVAL_LO,
    EXPECTED_ROW0_LABELS,
    TAN18_NUMERATOR_COEFFICIENTS,
    Interval,
    build_interval_certificate,
    certify_positive_tan_interval,
    evaluate_polynomial,
    verify_direction_order_at_infinity,
)


class NormalizeAndCertifyTest(unittest.TestCase):
    def _read_lines_rows(self) -> list[dict[str, str]]:
        with DEFAULT_LINES_PATH.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _write_lines_rows(self, path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames or ["m", "b"])
            writer.writeheader()
            writer.writerows(rows)

    def test_certified_m_radius_exceeds_the_preprint_presentation_radius(self) -> None:
        certificate = build_interval_certificate(DEFAULT_LINES_PATH, DEFAULT_OMATRIX_PATH)
        widths = set()
        for item in certificate["m_intervals"]:
            interval_lo, interval_hi = (Fraction(value) for value in item["interval"])
            widths.add(interval_hi - interval_lo)

        self.assertEqual(len(widths), 1)
        width = widths.pop()
        radius = width / 2
        self.assertGreater(radius, Fraction(1, 10**4))

    def test_tan_label_intervals_are_certified_by_exact_polynomial_sign_change(self) -> None:
        for k in range(1, 9):
            interval = certify_positive_tan_interval(k)
            self.assertLess(interval.lo, interval.hi)
            self.assertLess(
                evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, interval.lo)
                * evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, interval.hi),
                0,
            )

    def test_current_seed_data_normalizes_to_expected_bbl_shape(self) -> None:
        certificate = build_interval_certificate(DEFAULT_LINES_PATH, DEFAULT_OMATRIX_PATH)

        self.assertEqual(certificate["n"], 19)
        self.assertEqual(certificate["normalization"]["y0_line"], 0)
        self.assertEqual(certificate["normalization"]["order_for_rows_1_to_18"], "descending_y")
        self.assertEqual(certificate["normalization"]["special_lines"], [8, 15])
        self.assertEqual(certificate["row_order_inequalities_count"], 306)
        self.assertEqual(certificate["checked_rows"], list(range(1, 19)))
        self.assertTrue(certificate["omatrix_realized_by_bbl"])
        self.assertTrue(certificate["verdict"])
        self.assertEqual(certificate["normalization"]["interval_box_kind"], "positive_rational_box")

        labels = {item["line"]: item["label"] for item in certificate["a_values"]}
        self.assertEqual(labels[1], "-tan(8pi/18)")
        self.assertEqual(labels[8], "-epsilon")
        self.assertEqual(labels[15], "+epsilon")
        self.assertEqual(labels[18], "+tan(8pi/18)")
        self.assertEqual(certificate["diagnostics"]["normalization_mismatches"], [])

        epsilon_lo, epsilon_hi = (Fraction(value) for value in certificate["epsilon"]["interval"])
        self.assertEqual(epsilon_lo, EPSILON_INTERVAL_LO)
        self.assertEqual(epsilon_hi, Fraction(1, 10**4))

        for item in certificate["m_intervals"]:
            interval_lo, interval_hi = (Fraction(value) for value in item["interval"])
            self.assertGreater(interval_hi - interval_lo, 0)

        self.assertGreater(Fraction(certificate["row_order_min_margin"]), 0)
        self.assertGreater(Fraction(certificate["parallel_separation_min_margin"]), 0)
        self.assertGreater(Fraction(certificate["direction_order_at_infinity_min_margin"]), 0)
        self.assertTrue(certificate["diagnostics"]["direction_order_at_infinity"]["ok"])

        epsilon_zero_limit = certificate["diagnostics"]["epsilon_zero_limit"]
        self.assertTrue(epsilon_zero_limit["ok"])
        self.assertEqual(epsilon_zero_limit["negative_inequalities_count"], 0)
        self.assertEqual(epsilon_zero_limit["zero_inequalities_count"], 2)
        self.assertEqual(epsilon_zero_limit["required_zero_inequalities_count"], 2)

    def test_direction_order_at_infinity_uses_single_tan_pole_crossing(self) -> None:
        row0 = list(range(1, 19))
        label_by_line = {line_index: label for line_index, label in zip(row0, EXPECTED_ROW0_LABELS)}
        m_intervals = {0: Interval(Fraction(0), Fraction(0))}
        for line_index in range(1, 11):
            value = Fraction(-line_index, 10)
            m_intervals[line_index] = Interval(value, value)
        positive_values = [
            Fraction(8, 1),
            Fraction(7, 1),
            Fraction(6, 1),
            Fraction(5, 1),
            Fraction(4, 1),
            Fraction(3, 1),
            Fraction(2, 1),
            Fraction(1, 1),
        ]
        for line_index, value in zip(range(11, 19), positive_values):
            m_intervals[line_index] = Interval(value, value)

        diagnostics = verify_direction_order_at_infinity(row0, label_by_line, m_intervals)
        self.assertTrue(diagnostics["ok"])
        self.assertEqual(diagnostics["failures"], [])

        m_intervals[11] = Interval(Fraction(1, 2), Fraction(1, 2))
        m_intervals[12] = Interval(Fraction(3, 1), Fraction(3, 1))
        diagnostics = verify_direction_order_at_infinity(row0, label_by_line, m_intervals)
        self.assertFalse(diagnostics["ok"])
        self.assertTrue(any(item["kind"] == "positive_block_order" for item in diagnostics["failures"]))

    def test_normalization_rejects_csv_with_wrong_header(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            lines_path = Path(tmp_dir) / "bad_header_lines.csv"
            lines_path.write_text(DEFAULT_LINES_PATH.read_text(encoding="utf-8").replace("m,b", "slope,intercept", 1), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"must have CSV header \['m', 'b'\]"):
                build_interval_certificate(lines_path, DEFAULT_OMATRIX_PATH)

    def test_normalization_rejects_csv_without_y0_as_first_line(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            lines_path = Path(tmp_dir) / "bad_y0_lines.csv"
            rows = self._read_lines_rows()
            rows[0] = {"m": rows[1]["m"], "b": rows[1]["b"]}
            self._write_lines_rows(lines_path, rows)

            with self.assertRaisesRegex(ValueError, r"must start with Y_0 = y = 0"):
                build_interval_certificate(lines_path, DEFAULT_OMATRIX_PATH)

    def test_normalization_returns_false_verdict_when_row0_labels_no_longer_match_bbl_pattern(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            lines_path = Path(tmp_dir) / "shifted_anchor_lines.csv"
            rows = self._read_lines_rows()
            rows[1]["b"] = "-0.0116"
            self._write_lines_rows(lines_path, rows)

            certificate = build_interval_certificate(lines_path, DEFAULT_OMATRIX_PATH)

            self.assertFalse(certificate["omatrix_realized_by_bbl"])
            self.assertFalse(certificate["verdict"])
            self.assertTrue(certificate["diagnostics"]["normalization_mismatches"])

    def test_normalization_rejects_parallel_non_y0_lines(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            lines_path = Path(tmp_dir) / "parallel_lines.csv"
            rows = self._read_lines_rows()
            rows[2]["m"] = rows[1]["m"]
            self._write_lines_rows(lines_path, rows)

            with self.assertRaisesRegex(ValueError, r"failed to construct a positive initial interval radius"):
                build_interval_certificate(lines_path, DEFAULT_OMATRIX_PATH)


if __name__ == "__main__":
    unittest.main()
