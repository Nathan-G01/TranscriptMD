# TranscriptMD

Simple Python CLI tool to convert a YouTube transcript (`.txt` or one-column `.csv`) into clean Markdown.

## Example usage

**Single file** — title is provided as an argument:

```bash
python transcriptmd.py /path/to/transcript.txt "My Video Title"
```

```bash
python transcriptmd.py /path/to/transcript.csv "My Video Title" --output /path/to/output.md
```

**Recursive folder** (`-r`) — processes all `.txt`/`.csv` files in parallel; title is derived from each filename:

```bash
python transcriptmd.py -r /path/to/transcripts/ --output /path/to/output_folder/
```

```bash
python transcriptmd.py -r /path/to/transcripts/
# output folder defaults to ./transcripts_md/
```

## Output format

- `# <video title>`
- For each chapter:
  - `## <chapter title>`
  - one merged paragraph line for chapter text

Default output filename is generated from the title:

- lowercase
- spaces replaced with `_`
- `.md` suffix
