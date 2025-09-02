# Real Estate Scraper

A minimal toolkit for experimenting with property data extraction.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .[sqlite,test]
```

## Configuration

Environment variables in `.env` control the scraper’s behaviour, including
rate limiting, concurrency and proxy settings. See `.env.example` for all
available options.

## Usage

```bash
har2listings sample --har path/to/file.har
har2listings parse --har path/to/file.har --out out/listings.csv
har2listings parse-dir --har-dir ./hars --out out/listings.csv
har2listings export-sft-dpo --csv out/listings.csv --sft out/sft.jsonl --dpo out/dpo.jsonl
har2listings validate-csv --csv out/listings.csv
# increase verbosity with --log-level DEBUG on any command
```

## Testing

```bash
pytest
```
