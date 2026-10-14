# Velvet Dub — Implementation Plan

Product concept: `AI Dub & Filter Studio - Product Concept.pdf`. Brand: [BRAND.md](BRAND.md) (source of truth for all UI; original in `Velvet-Dub-Brand-Guidelines.pdf`).

## Scope and ground rules
- **Personal, private tool.** Runs locally on one Mac. No accounts, billing, public hosting, or sharing of titles or filter data. Revisit rights before any public release (dubbing/hosting copyrighted films is not covered by private-use filtering).
- **Phase 1 (MVP): filter + subtitles + watch.** **Phase 2: AI dubbing.** Phase 1 is built so Phase 2 only *adds* stages and files — no rewrites.
- The source file is never modified. Filtering is a timestamp list applied at playback.
- Analyze once, cache everything; changing language or filter settings later must be near-instant.

## Architecture

### Data on disk (per title)
```
data/titles/<title-id>/
  source.mp4
  audio/original.m4a        extracted audio (ffmpeg)
  transcript.json           segments: id, speaker, start, end, text, words[{w,start,end}], lang
  translations/<lang>.json  same segment ids + text + target_duration (used by dubbing)
  scan/visual.json          raw visual detections (before merging with spoken-word detections)
  filters.json              detections: {id, category, severity, start, end, confidence, source, note, text, region}
                            profile-independent; the action (mute/skip/blur) is decided at playback by the default rules and "Keep it in" choices
  subtitles/<lang>.vtt      complete, unfiltered; masking (*****) is applied at playback/export
  audio/<track>.m4a         Phase 2: dubbed tracks (original is the first track)
  manifest.json             stage status + list of audio tracks, subtitle tracks, filter file
```
`data/` is gitignored.

### Pipeline
Independent stages; each reads files, writes files, is skipped if its output exists and inputs are unchanged, and reports progress. Providers sit behind small interfaces (STT, Translator, Moderator, later TTS) so vendors swap via config.

| # | Stage | Phase |
|---|---|---|
| 1 | Extract audio (ffmpeg) | 1 |
| 2 | Transcribe + word timestamps + speaker labels | 1 |
| 3 | Visual scan: sample frames, classify nudity/sexual/violence/scary; scene cuts | 1 |
| 4 | Translate transcript (per target language; also emits `target_duration`) | 1 |
| 5 | Build `filters.json` (merge visual events + profanity from transcript) | 1 |
| 6 | Generate subtitles (.vtt, complete; filtered words masked at playback/export) | 1 |
| 7 | Separate vocals from music/effects (Demucs) | 2 |
| 8 | Synthesize speech per segment (TTS) | 2 |
| 9 | Fit to timing + mix with background → `audio/<lang>.m4a` | 2 |

### Stack
- **Pipeline/backend:** Python (uv), ffmpeg, FastAPI serving files + API, SQLite for profiles/settings/user corrections.
- **Web:** Vite + React + TypeScript (npm, Node 22). Styling from `BRAND.md` tokens (dark-only; Limelight + Archivo via Google Fonts).
- **Services:** transcription (API to start, e.g. AssemblyAI; local Whisper as a swap), Gemini Flash for visual moderation, Claude for translation. Phase 2: TTS provider (stock voices first).
- **Player:** HTML5 `<video>` over the source MP4 with Range requests. Video element is muted; the chosen audio track plays in a synced `<audio>` element — so adding a dub is adding a file. Filters applied live from `filters.json` + active profile: skip (seek past range), mute (gain 0), blur (overlay), summary card.

### Environment isolation (work machine — nothing global may change)
- **Python:** uv-managed 3.12 pinned in `.python-version`; deps in project `.venv/`. No global pip installs, no `--default` interpreter.
- **ffmpeg/ffprobe:** Homebrew ffmpeg 9.0.2 (already installed; it pulled in openssl@4 — see note below). The pipeline checks `ffmpeg`/`ffprobe` on PATH at startup and fails with a clear message if missing.
- **Node:** `.nvmrc` = 22 (via nvm; user default stays untouched). Use `npm` only — no corepack/pnpm. Deps in `web/node_modules/`.
- **Dev tools** (ruff, pytest, etc.) are dev dependencies, not global installs.
- **Caches/models** (Demucs, torch) redirected into `data/cache/` via env vars (`TORCH_HOME`, etc.).
- **Secrets:** project `.env` only, loaded first and overriding any shell variables (the shell `ANTHROPIC_API_KEY` may be a work key — don't use it). Personal accounts and billing for all providers, with spend limits. `.env`, `data/`, `.venv/`, `node_modules/` are gitignored; `.env.example` is committed with blank values.
- **Network:** dev servers bind to localhost only.
- **Known side effect:** `brew install ffmpeg` re-pointed Homebrew's default OpenSSL (`/opt/homebrew/include/openssl`, `lib/libssl.dylib`) to openssl@4; openssl@3 is still installed and used by existing formulae. If a native build elsewhere breaks, run `brew unlink openssl@4 && brew link openssl@3`.

### Repo layout
```
src/velvetdub/
  config/      Settings (env + .env; providers and models chosen by name)
  domain/      pure models and rules, no I/O: transcript, translation, filtering (+policy), presets,
               manifest, user, dubbing value types
  providers/   interfaces (base.py), per-kind registries, ProviderSet, one file per vendor, fakes
  pipeline/    Stage base, runner (caching, resume), observer, context, stages/
  storage/     TitleStore interface + filesystem implementation, TitlePaths, JSON artifacts
  media/       MediaTool interface + ffmpeg implementation
  auth/        IdentityProvider interface + local single-user implementation
  api/         FastAPI app factory, routers, dependencies
  subtitles/   WebVTT formatting
  container.py composition root: the only place concrete classes are chosen
  cli.py       `vd` command
tests/         pytest (fakes only: no network, keys or ffmpeg needed)
web/           React app (src/styles/tokens.css from BRAND.md; src/api/client.ts is the only API caller)
data/          gitignored
docs/          this plan, BRAND.md, original PDFs
```

### Engineering principles and extensibility
Design rule: **depend on interfaces, wire concrete classes in one place, keep rules separate from I/O.**

- **Features own the job; providers only connect.** `features/scene_filtering/` holds the prompt, the answer shape and the conversion into filter events; `features/translation/` holds the translation rules, batching and line checks. They call generic providers (`VideoAnalyzer`, `FrameJudge`, `TextGenerator`), so changing vendor never means rewriting prompts or film rules. Stages call features.
- **Providers are swappable.** Each capability (transcription, text generation, video analysis, text moderation, and for Phase 2 source separation and speech synthesis) is an abstract class in `providers/base.py`. `TRANSLATION_PROVIDER`/`MODEL` choose the text generator and `MODERATION_PROVIDER`/`MODEL` choose the video analyzer. Vendors are subclasses registered by name. Choosing a vendor or model is `.env` only (`TRANSCRIPTION_PROVIDER`, `TRANSLATION_MODEL`, `MODERATION_MODEL`, …). Adding a vendor = one new file plus a registered factory. No pipeline code changes. Each provider's `identity` (vendor:model) is part of its stage's cache key, so switching models automatically re-runs exactly the affected stages.
- **Providers are created lazily**, so a missing Phase 2 key never blocks Phase 1, and each command needs only the keys it uses.
- **Stages are plug-ins.** Phase 2 dubbing is new `Stage` subclasses (separate, synthesize, mix) added to the stage list; the runner, storage and existing stages are untouched.
- **Detection is separate from decision.** The pipeline stores viewer-independent detections. `FilterPolicy` + the default rules decide actions at playback, and "Keep it in" (per moment, or a whole category or severity level) is stored per title, so changing them never needs reprocessing. Filter profiles and presets were removed.
- **Multi-user is a seam, not a rewrite.** Every stored title and profile carries `owner_id`; every `TitleStore` call takes an owner id and treats other users' titles as not found; the API resolves the caller through `IdentityProvider` (today: always the local user). Going public means: a real `IdentityProvider` (sessions/OAuth), a database/object-storage `TitleStore`, a real job queue behind the stage runner, and the rights work. Routes, domain models and the pipeline do not change.
- **Storage and media are interfaces too** (`TitleStore`, `MediaTool`), so cloud storage or other tooling is another subclass.
- **Testing:** unit tests run entirely on fakes and temp directories; `.env` is never read in tests. The suite proves resume/caching, cache invalidation on model change, failure recording, owner isolation and identity swapping.
- **Quality gates:** `ruff` (lint + format), `mypy --strict`, `pytest` for Python; `tsc`, `oxlint`, `vitest` for the web app. All must pass before a step is called done.
- **Conventions:** small focused classes; pydantic models for all stored and API data (schema_version on the manifest for future migrations); errors derive from `VelvetDubError` with messages that say what to fix; secrets only via `.env`, never logged (`vd doctor` reports presence, never values).

## Phase 1 — Filter + subtitles (MVP)

**Goal:** add a film, get a filter timeline and subtitles, review it, watch it with filters applied live.

### 1.0 Foundations — DONE
- ✅ Repo scaffolded; tooling (uv, ruff, mypy, pytest; npm, vitest, oxlint); `.gitignore`; secrets only in `.env`.
- ✅ Domain models (transcript, translation, filtering + policy + presets, manifest, user), speaker and `target_duration` fields included.
- ✅ Provider interfaces, registries, lazy `ProviderSet`; stage runner with caching, progress, resume and failure recording; owner-scoped storage; identity seam; FastAPI skeleton (`/api/health`, `/api/titles`); `vd` CLI (`doctor`, `providers`, `process`, `titles`, `serve`); web shell with brand tokens.
- ✅ Stages 1–6 wired end to end and tested with fake providers.
- ✅ `CLAUDE.md` and README.
- Still skeleton (real implementation is step 1.1): the AssemblyAI, Claude and Gemini providers. TS types are hand-written for now (generate from the API schema when the surface grows).

### 1.1 Pipeline CLI on a single film (no UI) — BUILT, needs a real film to close
- Built: real AssemblyAI transcription (word timing + speakers, grouped into subtitle-sized lines), Claude translation (structured output, every line id validated, one retry for skipped lines), Gemini visual moderation (the pipeline cuts the film into 10-minute low-resolution clips; each clip is uploaded, analysed, deleted from the service, and its detections shifted onto the film's timeline), offline word-list profanity detection. `vd process <file> --subs en,es`; `vd doctor` checks setup.
- **Measured so far (7-second synthetic clip, real APIs):** all six stages in 17 s; word timing exact (muted word at 1.72–1.84 s); Spanish subtitles correct. Cost: a few cents. The synthetic picture contains nothing to detect, so **visual-scan accuracy is not yet measured**.
- **Still to do to close 1.1:** run one real film (with swearing and a tense scene). Record: total time, cost split by stage (visual scan expected to dominate), recall on nudity/violence/scary scenes, and compare `gemini-3.8-flash` against a flash-lite model. Tune for **recall over precision** (a miss costs more than an over-filter). Target: a 2-hour film in well under its runtime.
- Known limits: profanity detection is a small word list (no slurs/blasphemy list yet); no `--preset` option on the CLI (profiles apply at playback).

### 1.2 Player — DONE (verified in a real browser)
- Custom player per BRAND.md: stage-black stage, controls under a velvet rule, seek bar with signal marks for every filtered moment, 44 px targets, keyboard shortcuts (space/k, arrows, m, f). Media streamed with HTTP Range requests; the source file is never modified.
- Live filtering via `FilterEngine` (decides what happens at time t) and `PlaybackController` (applies it each animation frame): skip scene, mute word (with a small padding), blur (region or whole frame), "Skipped 42 s of violence" notice with "What happened?" and "Keep it in" (persisted per title). Overlapping skips merge into one jump.
- Verified by driving real Chrome: playhead jumped 10.01 s → 20.00 s over a skipped scene; audio muted 4.74–5.30 s around a 4.8–5.2 s word; "Keep it in" returned the playhead and played through; the choice persisted server-side.
- Subtitles: native tracks, language picker, words muted for the active profile masked as `*****` (server-side, per profile). **Limitation:** masking only works on text in the spoken language; translated subtitles are not masked yet. Dual-language subtitles and styling options are not built.
- Audio-track selector and synced external audio (for Phase 2 dubs) are built and unit-tested; with one track the selector is hidden.
- Not built yet (1.5): drapes/valance/curtain artwork; the "summarize" filter action has no UI.

### 1.3 Library, upload, review — DONE
- **Library:** titles with plain-language status ("Ready to watch", "Stopped at …"), duration, Review / Watch / Process actions.
- **Add a title:** upload streams the raw file to disk (never buffered in memory), then processing runs in the background (one film at a time) with per-stage progress ("The projector is warming up"), failure messages, and resume-from-where-it-stopped. **Deviation from plan:** uploads are not resumable and there is no "pick a local path" option (a path-taking endpoint would let any web page read local files); a dropped upload must be restarted.
- **Review ("Before the curtain goes up"):** filter timeline lanes with signal blocks, runtime removed, per-moment "Keep it in" / "Filter again" (kept moments drawn as dashed outlines, not by color alone), subtitle editor (spoken text beside editable lines, saves per line), SRT/VTT export (optionally masked), SRT/VTT import.
- **Corrections:** "Flag this moment" in the player stores "missed" / "shouldn't have been filtered" with time, category and note in SQLite (`data/velvetdub.db`). They are recorded only; nothing yet uses them to tune detection.
- **Local API protection:** requests must come from `127.0.0.1`/`localhost` (blocks DNS rebinding) and state-changing requests need a custom header (blocks other web pages). Ports are 8765 (API) and 5273 (web), with strict binding, to avoid colliding with other local projects.

### 1.4 Profiles and presets (dropped: see "Keep it in" on Review)
- Presets (Kids G / Family PG / Teen / Language only / Custom) and per-category sliders; profiles per household member with a PIN-locked parent profile.
- Settings apply at playback only — never reprocess.

### 1.5 Polish
- Full brand pass (sidebar, tokens, copy tone, empty and error states), accessibility checks (contrast, labels, keyboard), harbor placeholder art.

**Phase 1 done when:** you can add a film, review the filter timeline, switch profiles, and watch it with filters and subtitles working live, end to end, on your Mac.

## Phase 2 — AI dubbing

**Goal:** pick a language and get a new audio track that plays in the same player.

### 2.0 Prerequisites already in place from Phase 1
Speaker-labeled segments with durations; per-language translations with `target_duration`; audio-track list in the manifest; synced-audio player; provider interface slot for TTS.

### 2.1 Source separation
- Demucs (local; GPU-accelerated on Apple Silicon or CPU, or rented GPU if too slow) → `dialogue` and `background` stems. Background kept so only voices change.

### 2.2 Speech synthesis (stock voices first)
- TTS provider behind the interface; per-speaker voice assignment (stored in manifest; "The cast" UI lets you rename speakers and pick voices).
- Generate each segment's audio separately so single lines can be regenerated.

### 2.3 Length-aware fitting and mixing
- Translation already rephrases toward `target_duration`; measure synthesized length, re-prompt translation for over-long lines, small time-stretch only as a last resort.
- Place lines on the original timeline, mix over the background stem, loudness-normalize → `audio/<lang>.m4a`; add to manifest.
- Dub + filters: profanity is replaced at the *text* stage per profile before synthesis (kid-friendly translation tone); dub tracks are therefore per-language **and** per-filter-level, cached by key.

### 2.4 Script editor
- Line-by-line translation edit with "regenerate this line" (re-synthesizes one segment and re-mixes).

### 2.5 Player and UI
- Dub language picker alongside audio tracks; switch mid-playback keeping sync.

### 2.6 Later (only if it earns its place)
- Voice cloning per character ("match original voices"), emotion-aware voices, lip-sync (bought, premium), translation tone controls (literal / natural / kid-friendly).

**Phase 2 done when:** you can generate a dub for a film in a second language, edit and regenerate lines, and switch between original and dub during playback with filters still active.

## Cost expectations (per 2-hour film, estimates to verify)
- Transcription ~$0.50; translation ~$0.10–0.30/language; visual scan ~$1–10 (frame rate and model dependent).
- Phase 1 total ≈ $2–6 per film. Phase 2 adds ~$1–3 per language for stock voices ($10–20 if premium/cloned).

## Risks and open items
- **Rights:** private use only for now; revisit before sharing anything.
- **Missed content:** keep thresholds conservative; human review via the timeline before first watch.
- **Visual-scan accuracy/cost:** validate in 1.1 before building UI; fall back to cheaper sampling or a local classifier if costly.
- **Speaker diarization quality:** needed for Phase 2 voices; check accuracy in 1.1.
- **Open questions:** transcription provider (API vs local), test film, first languages, hardware limits for Demucs.

## Suggested order of work
1.0 → 1.1 (validate quality and cost) → 1.2 → 1.3 → 1.4 → 1.5 → Phase 2.
