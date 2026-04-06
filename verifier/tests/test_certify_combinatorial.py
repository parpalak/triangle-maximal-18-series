from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certify_combinatorial import (  # noqa: E402
    DEFAULT_CERTIFICATE_PATH,
    DEFAULT_OMATRIX_PATH,
    build_certificate,
    main,
)


class VerifierTest(unittest.TestCase):
    def _write_omatrix(self, path: Path, matrix: list[list[int]]) -> None:
        path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

    def test_current_seed_data_builds_combinatorial_certificate_from_public_omatrix(self) -> None:
        certificate = build_certificate(DEFAULT_OMATRIX_PATH)

        self.assertEqual(certificate["n"], 19)
        self.assertIn("omatrix_checksum", certificate)
        self.assertNotIn("interval_certificate_checksum", certificate)
        self.assertEqual(certificate["bounded_triangles"], 107)
        self.assertTrue(certificate["has_107_bounded_triangles"])
        self.assertEqual(certificate["touching_segments"], 17)
        self.assertTrue(certificate["touching_condition_on_Y0"])
        self.assertEqual(certificate["unused_segments_count"], 2)
        self.assertTrue(certificate["has_2_unused_segments"])
        self.assertTrue(certificate["verdict"])

    def test_structural_step_rejects_malformed_omatrix(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            omatrix_path = Path(tmp_dir) / "bad_omatrix.json"
            self._write_omatrix(omatrix_path, [[1, 2, 3]])

            with self.assertRaisesRegex(ValueError, "must be a JSON array with 19 rows"):
                build_certificate(omatrix_path)

    def test_structural_step_rejects_row_with_duplicate_index(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            matrix = json.loads(DEFAULT_OMATRIX_PATH.read_text(encoding="utf-8"))
            matrix[0] = matrix[0][:-1] + [matrix[0][0]]
            omatrix_path = Path(tmp_dir) / "duplicate_index_omatrix.json"
            self._write_omatrix(omatrix_path, matrix)

            with self.assertRaisesRegex(ValueError, r"row 0 must contain each index except 0 exactly once"):
                build_certificate(omatrix_path)

    def test_structural_step_returns_false_verdict_for_semantically_broken_but_well_formed_omatrix(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            matrix = json.loads(DEFAULT_OMATRIX_PATH.read_text(encoding="utf-8"))
            matrix[0] = [matrix[0][1], matrix[0][0], *matrix[0][2:]]
            omatrix_path = Path(tmp_dir) / "reversed_row_omatrix.json"
            self._write_omatrix(omatrix_path, matrix)

            certificate = build_certificate(omatrix_path)

            self.assertFalse(certificate["verdict"])
            self.assertFalse(certificate["touching_condition_on_Y0"])
            self.assertFalse(certificate["has_107_bounded_triangles"])

    def test_cli_default_output_path_is_combinatorial_certificate(self) -> None:
        original_contents = None
        if DEFAULT_CERTIFICATE_PATH.exists():
            original_contents = DEFAULT_CERTIFICATE_PATH.read_text(encoding="utf-8")

        try:
            with patch.object(sys, "argv", ["certify_combinatorial.py"]):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(DEFAULT_CERTIFICATE_PATH.exists())
            certificate = json.loads(DEFAULT_CERTIFICATE_PATH.read_text(encoding="utf-8"))
            self.assertTrue(certificate["verdict"])
        finally:
            if original_contents is None:
                if DEFAULT_CERTIFICATE_PATH.exists():
                    DEFAULT_CERTIFICATE_PATH.unlink()
            else:
                DEFAULT_CERTIFICATE_PATH.write_text(original_contents, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
