"""Minimal tests for TranscriptMD."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from transcriptmd import (
    generate_markdown,
    group_chapters,
    output_filename_from_title,
    read_input,
    remove_timestamps,
)


class TranscriptMDTests(unittest.TestCase):
    def test_full_pipeline_txt_to_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.txt"
            input_path.write_text(
                "Intro\n00:12\nThis   is   intro.\n\nDeep Dive\n01:33\nDetails here!\n",
                encoding="utf-8",
            )
            lines = read_input(input_path)
            without_timestamps = remove_timestamps(lines)
            chapters = group_chapters(without_timestamps)
            markdown = generate_markdown("My Video", chapters)

        self.assertIn("# My Video", markdown)
        self.assertIn("## Intro", markdown)
        self.assertIn("This is intro.", markdown)
        self.assertIn("## Deep Dive", markdown)
        self.assertIn("Details here!", markdown)

    def test_read_csv_one_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.csv"
            input_path.write_text(
                "Intro\n00:12\nText line\n\nNext\n01:22\nMore text\n", encoding="utf-8"
            )
            lines = read_input(input_path)
            without_timestamps = remove_timestamps(lines)
            chapters = group_chapters(without_timestamps)
        self.assertEqual(chapters[0][0], "Intro")
        self.assertEqual(chapters[1][0], "Next")

    def test_malformed_csv_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "bad.csv"
            input_path.write_text("a,b\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Malformed CSV"):
                read_input(input_path)

    def test_empty_after_timestamps_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Empty transcript"):
            remove_timestamps(["00:10", "01:20"])

    def test_output_filename_from_title(self) -> None:
        self.assertEqual(output_filename_from_title("My Cool Video"), "my_cool_video.md")


if __name__ == "__main__":
    unittest.main()
