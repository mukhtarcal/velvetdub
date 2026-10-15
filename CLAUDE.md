# Velvet Dub

Personal, private tool: filter, subtitle and (Phase 2) dub films. Runs locally on one Mac.

Read first: `docs/PLAN.md` (phases, architecture, extensibility rules) and `docs/BRAND.md` (all UI must follow it; the PDFs in `docs/` are the visual originals). Approved screen designs live in `docs/design/<name>/`, each with a `README.md` spec; read the matching one before changing those screens.

## Commands
- Python (from repo root; never use pip or global installs): `uv sync`, `uv run pytest`, `uv run ruff check . && uv run ruff format .`, `uv run mypy`
- CLI: `uv run vd --help` (`doctor`, `providers`, `process <file> --subs en,es`, `titles`, `serve`)
- Run the app: `./dev.sh` from the repo root starts the API and the web app together (Ctrl+C stops both), then open http://127.0.0.1:5273. It installs `web/node_modules` on first run.
- Web: `source ~/.nvm/nvm.sh && nvm use 22` then `npm --prefix web run dev|build|lint|test` (npm only, no pnpm)
- API on 127.0.0.1:8765 (`uv run vd serve`), web on 127.0.0.1:5273 (Next.js rewrites `/api/*` to the API in `web/next.config.ts`). Unusual ports on purpose: other local projects use 8000/5173.
- Web stack: Next.js (App Router, client-rendered pages) + Tailwind v4 + shadcn/ui (Radix) + Motion. Brand tokens live in `web/src/styles/tokens.css` and are mapped to shadcn's names in `web/src/app/globals.css`; theatre motifs (curtains, valance, grain) in `web/src/styles/stage.css`. Pages are thin wrappers in `web/src/app/`; screens live in `web/src/components/views/`. `web/src/api`, `lib`, `hooks` and `player` are framework-free.
- Next.js here is newer than most training data: read `web/node_modules/next/dist/docs/` before changing config or routing. `cacheComponents` is off on purpose (it keeps old pages mounted, which would leave a film playing out of sight).

## Rules
- **Work machine: change nothing global.** Everything installs inside this folder (`.venv`, `web/node_modules`). No `brew install`, `npm -g`, or edits outside the repo without asking.
- **Secrets only in `.env`** (gitignored). Never print, log or commit key values. The project `.env` overrides the shell on purpose (the shell `ANTHROPIC_API_KEY` may be a work key). Tests must never read `.env` (`Settings(_env_file=None)`).
- **Depend on interfaces; wire concrete classes only in `container.py`.** New vendor = new file in `providers/` + registered factory; selection is `.env`. New pipeline step = new `Stage`, added in `pipeline/stages/__init__.py`.
- **Features own the job; providers only connect.** What to ask a model and what to do with the answer (prompts, result shapes, validation, retries of bad answers) lives in `features/<name>/` (`scene_filtering`, `translation`). `providers/` holds vendor connections only (upload, call, retry, quota, token counts) behind generic interfaces (`TextGenerator`, `VideoAnalyzer`, `Transcriber`). No prompts or film rules in `providers/`. The scene scan has two scanners picked by `MODERATION_PROVIDER`: a video model (`gemini`, whole clips) or a frame judge (`openai`, Decisions API, a few frames at a time, nudity and sexual content only). Stages stay thin: pick a feature, give it a provider, save files.
- **Detection vs decision:** stored filter events are viewer-independent; `FilterPolicy` applies the default rules (`domain/rules.py`: mute words, skip scenes) plus the viewer's per-title "Keep it in" choices at playback. There are no filter profiles or presets. Don't bake actions into stored detections.
- **Multi-user seam:** every owned record has `owner_id`; storage calls take an owner id; the API gets the user from `IdentityProvider`. Don't hardcode the local user outside the CLI and `LocalIdentityProvider`.
- The source video is never modified; filters are timestamp lists applied at playback. The one exception in kind is the downloadable cleaned copy (`services/exports.py`): a separate derived file in the title's `exports/` folder, made on request from the current cuts and discarded when they change.
- Domain layer (`domain/`) is pure: no I/O, no vendor SDKs.
- Done means: ruff, mypy (strict), pytest, and for web `build`, `lint`, `test` all pass.
- Copy and UI follow `docs/BRAND.md` (dark only, square corners, one primary button per screen, signal red only for active filters, no emoji, plain words in anything actionable).
- Don't commit or push unless asked.
