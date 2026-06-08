"""TranscriptMD: convert YouTube transcript files into Markdown."""

from __future__ import annotations

import argparse
import csv
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence


TIMESTAMP_PATTERN = re.compile(r"^\s*\d+:[0-5]\d\s*$")
TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\s*\d+:[0-5]\d\s*(.+)\s*$")
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


def parse_transcript(lines: Sequence[str]) -> list[tuple[str, str]]:
    """Parse raw transcript lines into (title, body) chapters.

    A plain-text line not preceded by a timestamp is a chapter title.
    Body content before the first explicit title is labelled 'Introduction'.
    """
    chapters: list[tuple[str, str]] = []
    current_title: str | None = None
    current_body: list[str] = []
    prev_was_timestamp = False

    for line in lines:
        if not line:
            prev_was_timestamp = False
            continue

        if TIMESTAMP_PATTERN.match(line):
            prev_was_timestamp = True
            continue

        match = TIMESTAMP_PREFIX_PATTERN.match(line)
        if match:
            text = normalize_whitespace(match.group(1))
            if text:
                current_body.append(text)
            prev_was_timestamp = False
            continue

        if prev_was_timestamp:
            current_body.append(line)
        else:
            if current_title is not None or current_body:
                body = normalize_whitespace(" ".join(current_body))
                title = current_title if current_title is not None else "Introduction"
                if body:
                    chapters.append((title, body))
            current_title = line
            current_body = []

        prev_was_timestamp = False

    if current_title is not None or current_body:
        body = normalize_whitespace(" ".join(current_body))
        title = current_title if current_title is not None else "Introduction"
        if body:
            chapters.append((title, body))

    if not chapters:
        raise ValueError("No chapters found in transcript.")
    return chapters


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


def title_from_stem(stem: str) -> str:
    """Derive a human-readable title from a file stem."""
    return stem.replace("_", " ").replace("-", " ").strip()


def _process_file(args: tuple[Path, Path]) -> tuple[Path, str | None]:
    """Worker: convert one transcript file to Markdown. Returns (output_path, error|None)."""
    input_path, output_path = args
    try:
        lines = read_input(input_path)
        chapters = parse_transcript(lines)
        markdown = generate_markdown(title_from_stem(input_path.stem), chapters)
        write_output(markdown, output_path)
        return output_path, None
    except Exception as exc:
        return output_path, str(exc)


def process_folder(input_folder: Path, output_folder: Path) -> None:
    """Convert all .txt/.csv files in input_folder to Markdown files in output_folder."""
    files = sorted(p for p in input_folder.iterdir() if p.suffix.lower() in {".txt", ".csv"})
    if not files:
        raise ValueError(f"No .txt or .csv files found in {input_folder}.")

    output_folder.mkdir(parents=True, exist_ok=True)
    tasks = [(f, output_folder / (f.stem + ".md")) for f in files]

    workers = os.cpu_count() or 1
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_input = {executor.submit(_process_file, task): task[0] for task in tasks}
        for future in as_completed(future_to_input):
            input_path = future_to_input[future]
            output_path, error = future.result()
            if error:
                print(f"ERROR {input_path.name}: {error}", flush=True)
            else:
                print(f"Written: {output_path}", flush=True)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="TranscriptMD",
        description="Convert a YouTube transcript file (.txt/.csv) into Markdown.",
    )
    parser.add_argument(
        "input",
        help="Path to input transcript (.txt or .csv), or a folder when using -r.",
    )
    parser.add_argument(
        "video_title",
        nargs="?",
        help="Video title for the Markdown # heading (omit when using -r).",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process all .txt/.csv files in a folder in parallel.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output file path (single mode) or output folder (recursive mode). "
            "Defaults to a generated filename / '<input>_md' folder."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    input_path = Path(args.input)

    if args.recursive:
        if not input_path.is_dir():
            raise SystemExit(f"Error: '{input_path}' is not a directory. -r requires a folder.")
        output_folder = (
            Path(args.output) if args.output else Path.cwd() / (input_path.name + "_md")
        )
        process_folder(input_folder=input_path, output_folder=output_folder)
    else:
        if not args.video_title:
            raise SystemExit("Error: video_title is required when not using -r.")
        lines = read_input(input_path)
        chapters = parse_transcript(lines)
        markdown = generate_markdown(args.video_title, chapters)
        output_path = (
            Path(args.output)
            if args.output
            else Path.cwd() / output_filename_from_title(args.video_title)
        )
        written_to = write_output(markdown, output_path)
        print(f"Markdown written to: {written_to}")


if __name__ == "__main__":
    main()
