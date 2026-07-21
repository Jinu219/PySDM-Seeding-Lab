from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analysis.release_candidate import validate_v1_release_candidate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleaseCandidateTests(unittest.TestCase):
    def test_repository_is_a_complete_v1_release_candidate(self) -> None:
        report = validate_v1_release_candidate(PROJECT_ROOT)
        self.assertTrue(report["ready"])
        self.assertEqual(report["version"], "1.0.0")
        self.assertEqual(report["blog_checkpoint"], "before_merge")
        self.assertEqual(report["merge_source"], "develop")
        self.assertEqual(report["merge_target"], "main")

    def test_missing_release_files_are_rejected_before_other_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "missing required files"):
                validate_v1_release_candidate(temporary_directory)


if __name__ == "__main__":
    unittest.main()
