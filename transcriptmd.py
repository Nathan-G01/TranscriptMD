"""TranscriptMD: convert YouTube transcript files into Markdown."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Sequence


TIMESTAMP_PATTERN = re.compile(r"^\s*\d{1,2}:[0-5]\d\s*$")
TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\s*\d{1,2}:[0-5]\d\s+(.+?)\s*$")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs into single spaces."""
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def read_input(input_path: Path) -> list[str]:
    """Read transcript lines from .txt or one-column .csv input."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise ValueError(
            f"Unsupported input extension '{input_path.suffix}'. Use .txt or .csv."
        )

    if suffix == ".txt":
        content = input_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    else:
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            lines = []
            for row_index, row in enumerate(reader, start=1):
                if len(row) == 0:
                    lines.append("")
                    continue
                if len(row) != 1:
                    raise ValueError(
                        f"Malformed CSV: expected exactly one column at row {row_index}."
                    )
                lines.append(row[0])

    cleaned = [normalize_whitespace(line) for line in lines]
    if not any(cleaned):
        raise ValueError("Empty transcript: no usable content found.")
    return cleaned


def remove_timestamps(lines: Sequence[str]) -> list[str]:
    """Remove pure mm:ss lines and strip leading mm:ss when followed by text."""
    filtered: list[str] = []
    for line in lines:
        if TIMESTAMP_PATTERN.match(line):
            continue
        match = TIMESTAMP_PREFIX_PATTERN.match(line)
        if match:
            filtered.append(normalize_whitespace(match.group(1)))
            continue
        filtered.append(line)
    if not any(filtered):
        raise ValueError("Empty transcript after removing timestamp lines.")
    return filtered


def group_chapters(lines: Sequence[str]) -> list[tuple[str, str]]:
    """Split transcript by empty lines and return (title, merged text) chapters."""
    chapters: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line == "":
            if current:
                chapters.append(current)
                current = []
            continue
        current.append(line)
    if current:
        chapters.append(current)

    output: list[tuple[str, str]] = []
    for chapter_index, chapter_lines in enumerate(chapters, start=1):
        title = chapter_lines[0]
        if not title:
            raise ValueError(f"Chapter {chapter_index} is missing a title.")
        body = normalize_whitespace(" ".join(chapter_lines[1:]))
        if not body:
            raise ValueError(f"Chapter {chapter_index} has no body text after the title.")
        output.append((title, body))

    if not output:
        raise ValueError("No chapters found in transcript.")
    return output


def generate_markdown(video_title: str, chapters: Sequence[tuple[str, str]]) -> str:
    """Build the Markdown document from title and chapter tuples."""
    heading = normalize_whitespace(video_title)
    if not heading:
        raise ValueError("Video title cannot be empty.")

    parts = [f"# {heading}", ""]
    for chapter_title, chapter_text in chapters:
        parts.append(f"## {chapter_title}")
        parts.append(chapter_text)
        parts.append("")
    markdown = "\n".join(parts).rstrip() + "\n"
    if not markdown.strip():
        raise ValueError("Generated Markdown output is empty.")
    return markdown


def output_filename_from_title(video_title: str) -> str:
    """Generate output filename from title: lowercase, spaces to underscores, .md."""
    normalized = normalize_whitespace(video_title)
    if not normalized:
        raise ValueError("Video title cannot be empty.")
    return normalized.lower().replace(" ", "_") + ".md"


def write_output(markdown: str, output_path: Path) -> Path:
    """Write Markdown content to disk in UTF-8."""
    if not markdown.strip():
        raise ValueError("Refusing to write empty output.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="TranscriptMD",
        description="Convert a YouTube transcript file (.txt/.csv) into Markdown.",
    )
    parser.add_argument("input_file", help="Path to input transcript (.txt or .csv).")
    parser.add_argument("video_title", help="Video title for the Markdown # heading.")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output file path. Defaults to generated filename in current directory.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()

    input_path = Path(args.input_file)
    video_title = args.video_title

    lines = read_input(input_path)
    lines_without_timestamps = remove_timestamps(lines)
    chapters = group_chapters(lines_without_timestamps)
    markdown = generate_markdown(video_title, chapters)

    output_path = (
        Path(args.output)
        if args.output
        else Path.cwd() / output_filename_from_title(video_title)
    )
    written_to = write_output(markdown, output_path)
    print(f"Markdown written to: {written_to}")


if __name__ == "__main__":
    main()
