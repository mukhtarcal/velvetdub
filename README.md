# Velvet Dub

A movie palace in your living room. A personal tool that filters, subtitles and (later) dubs films and shows.

Start with [docs/PLAN.md](docs/PLAN.md). Brand reference: [docs/BRAND.md](docs/BRAND.md).

## Setup (everything stays inside this folder)

```bash
cp .env.example .env        # then fill in the three API keys
uv sync                     # Python 3.12 + dependencies into .venv
source ~/.nvm/nvm.sh && nvm use 22
npm --prefix web install
uv run vd doctor            # checks ffmpeg, keys and providers
```

## Run

```bash
uv run vd serve                         # API on http://127.0.0.1:8765
npm --prefix web run dev                # web on http://127.0.0.1:5273
uv run vd process path/to/film.mp4 --subs en,es
```

## Check

```bash
uv run ruff check . && uv run mypy && uv run pytest
npm --prefix web run build && npm --prefix web run lint && npm --prefix web test
```

Providers and models are selected in `.env`; see `uv run vd providers`.
