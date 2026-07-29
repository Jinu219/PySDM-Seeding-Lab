from __future__ import annotations

import io
import json
import unittest
import zipfile

from analysis.plot_downloads import build_plot_zip_bytes, safe_plot_stem


class PlotDownloadTests(unittest.TestCase):
    def test_safe_plot_stem_removes_path_and_punctuation_characters(self):
        self.assertEqual(
            safe_plot_stem("../rain water: diff?"),
            "rain_water_diff",
        )
        self.assertEqual(safe_plot_stem("***", fallback="figure"), "figure")

    def test_plot_zip_contains_numbered_pngs_and_title_manifest(self):
        payloads = [
            ("Rain response", b"first-png"),
            ("Rain response", b"second-png"),
            ("구름 물 변화", b"third-png"),
        ]

        archive_bytes = build_plot_zip_bytes(payloads)

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            filenames = archive.namelist()
            self.assertEqual(
                filenames,
                [
                    "01_Rain_response.png",
                    "02_Rain_response.png",
                    "03_구름_물_변화.png",
                    "manifest.json",
                ],
            )
            self.assertEqual(
                archive.read("02_Rain_response.png"),
                b"second-png",
            )
            manifest = json.loads(archive.read("manifest.json"))

        self.assertEqual(manifest["plot_count"], 3)
        self.assertEqual(manifest["plots"][2]["title"], "구름 물 변화")

    def test_plot_zip_is_reproducible(self):
        payloads = [("A", b"a"), ("B", b"b")]
        self.assertEqual(
            build_plot_zip_bytes(payloads),
            build_plot_zip_bytes(payloads),
        )

    def test_plot_zip_rejects_non_bytes_payload(self):
        with self.assertRaisesRegex(TypeError, "bytes-like"):
            build_plot_zip_bytes([("invalid", "not-bytes")])


if __name__ == "__main__":
    unittest.main()
