"""Minimal tests for TranscriptMD."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from transcriptmd import (
    generate_markdown,
    group_chapters,
    normalize_whitespace,
    output_filename_from_title,
    parse_transcript,
    process_folder,
    read_input,
    remove_timestamps,
    title_from_stem,
    write_output,
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

    def test_normalize_whitespace(self) -> None:
        self.assertEqual(normalize_whitespace("  a\t b\n\n c  "), "a b c")

    def test_write_output_creates_parent_and_writes_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "out.md"
            written_path = write_output("# Héllo\n", output_path)

            self.assertEqual(written_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# Héllo\n")

    def test_write_output_rejects_empty_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "out.md"
            with self.assertRaisesRegex(ValueError, "empty output"):
                write_output("   ", output_path)

    def test_remove_timestamps_strips_leading_timestamp_from_text(self) -> None:
        cleaned = remove_timestamps(
            ["00:00 Intro", "00:04 This is the intro", "", "01:15 Deep Dive"]
        )
        self.assertEqual(cleaned, ["Intro", "This is the intro", "", "Deep Dive"])

    def test_remove_timestamps_keeps_non_timestamp_text(self) -> None:
        lines = ["Intro", "This is plain text", "", "Deep Dive", "More details"]
        self.assertEqual(remove_timestamps(lines), lines)

    def test_remove_timestamps_handles_extra_space_after_timestamp(self) -> None:
        cleaned = remove_timestamps(["00:00   Intro text", "01:02      More text"])
        self.assertEqual(cleaned, ["Intro text", "More text"])

    def test_remove_timestamps_supports_long_minute_timestamps(self) -> None:
        cleaned = remove_timestamps(["100:00", "125:07 Long form content"])
        self.assertEqual(cleaned, ["Long form content"])

    def test_remove_timestamps_accepts_no_space_after_timestamp(self) -> None:
        cleaned = remove_timestamps(["1:23No-space text"])
        self.assertEqual(cleaned, ["No-space text"])

    def test_parse_transcript_title_not_preceded_by_timestamp(self) -> None:
        lines = [
            "1:10",
            "some body text",
            "Building the JWT Token Provider",
            "1:15",
            "more body text",
        ]
        chapters = parse_transcript(lines)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0][0], "Introduction")
        self.assertIn("some body text", chapters[0][1])
        self.assertEqual(chapters[1][0], "Building the JWT Token Provider")
        self.assertIn("more body text", chapters[1][1])

    def test_parse_transcript_title_at_start(self) -> None:
        lines = ["Intro", "0:05", "body one", "Next Section", "0:10", "body two"]
        chapters = parse_transcript(lines)
        self.assertEqual(chapters[0][0], "Intro")
        self.assertEqual(chapters[1][0], "Next Section")

    def test_parse_transcript_intro_defaults_to_introduction(self) -> None:
        lines = ["0:00", "first line", "0:03", "second line", "Chapter One", "0:07", "chapter body"]
        chapters = parse_transcript(lines)
        self.assertEqual(chapters[0][0], "Introduction")
        self.assertEqual(chapters[1][0], "Chapter One")

    def test_title_from_stem_underscores_and_hyphens(self) -> None:
        self.assertEqual(title_from_stem("building_jwt_token"), "building jwt token")
        self.assertEqual(title_from_stem("my-video-title"), "my video title")
        self.assertEqual(title_from_stem("mixed_and-both"), "mixed and both")

    def test_process_folder_creates_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_folder = Path(temp_dir) / "transcripts"
            output_folder = Path(temp_dir) / "output"
            input_folder.mkdir()

            (input_folder / "video_one.txt").write_text(
                "0:00\nintro content\nChapter One\n0:05\nbody text\n", encoding="utf-8"
            )
            (input_folder / "video_two.txt").write_text(
                "0:00\nother intro\nChapter Two\n0:05\nmore body\n", encoding="utf-8"
            )

            process_folder(input_folder, output_folder)

            self.assertTrue((output_folder / "video_one.md").exists())
            self.assertTrue((output_folder / "video_two.md").exists())
            content = (output_folder / "video_one.md").read_text(encoding="utf-8")
            self.assertIn("# video one", content)
            self.assertIn("## Chapter One", content)

    def test_process_folder_empty_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_folder = Path(temp_dir) / "empty"
            input_folder.mkdir()
            with self.assertRaisesRegex(ValueError, "No .txt or .csv files"):
                process_folder(input_folder, Path(temp_dir) / "out")

    def test_process_folder_skips_non_transcript_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_folder = Path(temp_dir) / "mixed"
            output_folder = Path(temp_dir) / "output"
            input_folder.mkdir()

            (input_folder / "transcript.txt").write_text(
                "0:00\nintro\nSection\n0:05\nbody\n", encoding="utf-8"
            )
            (input_folder / "readme.md").write_text("# ignore me\n", encoding="utf-8")
            (input_folder / "data.json").write_text("{}", encoding="utf-8")

            process_folder(input_folder, output_folder)

            self.assertTrue((output_folder / "transcript.md").exists())
            self.assertFalse((output_folder / "readme.md").exists())
            self.assertFalse((output_folder / "data.md").exists())


if __name__ == "__main__":
    unittest.main()
