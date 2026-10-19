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
| 7 | `separate`: split dialogue from music/effects (Demucs) | 2 |
| 8 | `dub_transcribe`: transcribe the dialogue stem alone, merged into whole sentences | 2 |
| 9 | `dub_translate`: write the dub script per language, timed to each original line | 2 |
| 10 | `dub_voices`: copy each speaker's voice from the clean dialogue (Cartesia) | 2 |
| 11 | `dub_speech`: speak every line, fitted to its room; cached per line | 2 |
| 12 | `dub_mix`: lay the lines over the background → `audio/dub-<lang>.m4a` | 2 |

The six dubbing stages do nothing (and cost nothing) unless a dub language was asked for.

### Stack
- **Pipeline/backend:** Python (uv), ffmpeg, FastAPI serving files + API, SQLite for profiles/settings/user corrections.
- **Web:** Next.js (App Router) + React + TypeScript + Tailwind + shadcn/ui + Motion (npm, Node 22). Styling from `BRAND.md` tokens (dark-only; Limelight + Archivo via `next/font`). Next.js forwards `/api` to the local API.
- **Services:** transcription (API to start, e.g. AssemblyAI; local Whisper as a swap), Gemini Flash for visual moderation, Claude for translation. Phase 2: TTS provider (stock voices first).
- **Player:** HTML5 `<video>` over the source MP4 with Range requests. Video element is muted; the chosen audio track plays in a synced `<audio>` element — so adding a dub is adding a file. Filters applied live from `filters.json` + active profile: skip (seek past range), mute (gain 0), blur (overlay), summary card.

### Environment isolation (work machine — nothing global may change)
- **Python:** uv-managed 3.12 pinned in `.python-version`; deps in project `.venv/`. No global pip installs, no `--default` interpreter.
- **ffmpeg/ffprobe:** found on PATH or in `.venv/bin` (the project's static build; `vd doctor` reports `ok`). Homebrew ffmpeg 9.0.2 was installed earlier and pulled in openssl@4 — see note below. The pipeline checks `ffmpeg`/`ffprobe` on PATH at startup and fails with a clear message if missing.
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
               (dubbing: cartesia.py for voices, demucs.py for separation)
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
- **Local API protection:** requests must come from `127.0.0.1`/`localhost` (blocks DNS rebinding) and state-changing requests need a custom header (blocks other web pages). **Film uploads go straight from the browser to the API (port 8765), not through the web app's `/api` proxy:** Next.js copies a proxied request body into memory and cuts it off at 10 MB, so a film sent through it never arrived whole (found 2026-10-18; the old Vite proxy streamed). The API therefore approves cross-origin POSTs from the web app's own two addresses only (`web_origins` in settings, POST only, custom header still required), and every other site is still refused. Do not raise Next's `proxyClientMaxBodySize` to fix uploads: it would hold the whole film in RAM. Ports are 8765 (API) and 5273 (web), with strict binding, to avoid colliding with other local projects.

### 1.4 Profiles and presets (dropped: see "Keep it in" on Review)
- Presets (Kids G / Family PG / Teen / Language only / Custom) and per-category sliders; profiles per household member with a PIN-locked parent profile.
- Settings apply at playback only — never reprocess.

### 1.5 Polish
- Full brand pass (sidebar, tokens, copy tone, empty and error states), accessibility checks (contrast, labels, keyboard), harbor placeholder art.

**Phase 1 done when:** you can add a film, review the filter timeline, switch profiles, and watch it with filters and subtitles working live, end to end, on your Mac.

## Phase 2 — AI dubbing

### Only what is chosen is run (2026-10-18)
Nothing is processed by default; every step runs only when a choice needs it. Choosing **nothing** stores the film and records its length, with no transcription, scan, translation or voices (and no keys needed). **Swearing is now a fifth filter choice, off by default** (it used to run on every film, which meant every film was transcribed). Transcription (the film's own mix) runs only for swearing or subtitles; a dub transcribes the separated dialogue itself, so a dub alone no longer transcribes the mix as well. Per-step rules are in `docs/design/add-title-redesign/README.md` ("Only what is chosen is run"). Consequence: a film with nothing chosen has no swearing mutes at playback, because none were looked for; Review says so.

### Status (2026-10-18)
**Built: choose a dubbing language next to subtitles, and get a dub as a new audio track.** Add a title has an optional **Dubbing** section (same pattern as Subtitles: off by default, language chips, never shown as available unless this install can dub). `vd process <file> --dub ar` does the same from the CLI. Run on the 146 s sample through the real services: all twelve stages in 56 s, 15 sentences, no line over its room, two copied voices, a 145.8 s track for a 145.8 s film. Engine decision: **Cartesia** (voice copying + Arabic, native speed control, best fit and round trip in the spikes). Setup: `uv sync --group dubbing` (Demucs, torch) and `CARTESIA_API_KEY` in `.env`; `vd doctor` reports both as optional.

How it is built (all of it follows the rules above):
- `features/dubbing/`: `sentences.py` (merge pause-sized lines into whole sentences), `timing.py` (each line's room: its length plus up to 1 s into the pause after it, never into the next line), `samples.py` + `cast.py` (about 15 s of clear speech per speaker; a barely heard speaker borrows the main voice), `speech.py` (record at natural pace, ask for faster up to the service's cap, then squeeze at most 1.2x; a line that still runs long is kept and pushes the next back), `lines.py` (parallel recording; each line's file is named after its text, voice, room and service, so a stopped run resumes and an edit re-records one line), `support.py` (which languages this install can dub).
- `providers/`: `cartesia.py` (clone, speak, delete; retry on busy, quota message, never prints the key) and `demucs.py` (5-minute pieces so a long film fits in memory; weights in `data/cache/`) behind `SpeechSynthesizer` (now with optional `clone_voice`/`delete_voice`, `max_speed`, `languages()`) and `SourceSeparator`. Fakes for both.
- `media/dialogue.py` joins lines into one track with plain WAV handling (no ffmpeg, constant memory); `MediaTool` gained `extract_mix`, `cut_audio`, `change_tempo`, `mix_dub`.
- Subtitles and dubs are translated separately (a dub is written to be spoken and from the cleaner transcript), so `TranslateStage` now handles subtitle languages only. A film is never dubbed into the language it is already in (known only after transcription, so the voices are separated and transcribed first; no voice is copied or spoken).
- API: `dub_languages` on the process request (refused in plain words when unsupported or not set up) and in `/api/capabilities`; titles remember `choices.dub_languages`; the dub is just another entry in `audio_tracks` ("Arabic dub"), so the existing player selector shows it. Dub stages are listed in the progress view only for a title that asked for a dub.

**Not built yet (known limits):**
- A **whole film has not been run.** Timing and memory were designed for it (chunked separation, per-line resume) but only the 146 s clip was measured: separation was about 0.3x runtime in the spike, speech cost scales with dialogue length. Run one real film before relying on it, and check credits first.
- **Only Cartesia and Demucs** exist. Kokoro, Piper, macOS `say`, XTTS and ElevenLabs were spikes only; there is no stock-voice fallback, so a service that cannot copy voices is refused.
- **Cloned voices stay on the Cartesia account** (private). Delete them there when a film is finished; `SpeechSynthesizer.delete_voice` exists but nothing calls it yet.
- No **script editor / regenerate one line** UI (2.4) and no **cast screen** to rename speakers or choose voices (2.2); no design exists for either.
- A dub is **not filtered at the text stage** (the old per-profile idea): swearing stays in the dub, but the usual timestamp mutes and skips still apply to the dub track in the player because lines sit at the original times. Cutting the film (the cleaned copy export) does not yet carry the dub.
- The player lists the dub as an audio track but there is **no dub-specific picker** (2.5), and the dub is never selected by default.
- Which language to dub is not checked against the film's language until after transcription; Cartesia's cross-language voice copying (English sample speaking Arabic) was judged only by the round-trip test, not by ear.

**Goal:** pick a language and get a new audio track that plays in the same player.

### 2.0 Prerequisites already in place from Phase 1
Speaker-labeled segments with durations; per-language translations with `target_duration` (the translator already has a tone setting but does not yet use the duration to shorten lines); audio-track list in the manifest; synced-audio player (selector hidden while there is one track); `SourceSeparator` and `SpeechSynthesizer` interfaces with `TTS_PROVIDER`, `TTS_MODEL`, `SEPARATION_PROVIDER` settings, created lazily.

Still missing: any separation or TTS vendor, the three stages, per-speaker voice assignment, dub UI (no approved designs yet: The cast, script editor, dub picker), and a rule for how dubs and filters combine now that profiles are gone (see 2.3).

### 2.0a Free first, paid as the fallback
Dubbing starts with **no paid services**: local separation and local speech. ElevenLabs (key slot already in settings) is the fallback if free voices are not good enough, and slots in as one more `SpeechSynthesizer`. Translation keeps using Claude (already paid for Phase 1).
- **Quality bar for leaving free:** a native listener says the voices are understandable and the pacing is natural enough to watch a whole film. Measure on the sample clip first (below), then decide.
- Dubbing dependencies go in an optional uv group (`dubbing`: torch, Demucs, the TTS engine) so Phase 1 installs stay light. All of it lives in `.venv`; model weights go to `data/cache/`.

### 2.0b Spike on one clip before building stages
Sample: `data/samples/dubbing_test.mp4` (gitignored; 2:26, 3840x1602, stereo AAC). Run by hand, no UI: extract audio → Demucs → transcribe → translate → synthesize → fit → mix → mux over the picture and watch it. Record, per step: wall time, memory, cost, and what sounded wrong. The spike decides the TTS engine, the fitting rule and whether Demucs is fast enough on this Mac. Stage design (2.1–2.3) is revised from what the spike finds.

**Spike 1 results (English → Spanish, Demucs `htdemucs` on Apple GPU, Kokoro `em_alex`/`em_santa`, 2026-10-15):**
- **Speed (146 s clip):** Demucs 47 s (about 0.3x runtime; a 2-hour film is roughly 40 min, so background only). Kokoro 9 s for 22 lines (about 0.4 s a line) after a one-time model download. Transcription 7 s, translation 5 s, mix and mux under 25 s. Cost: transcription and translation cents; separation and speech free.
- **Transcribe the dialogue stem, not the original mix.** With loud music, word timings on the original audio were wrong ("Everything" stretched to 7.5 s, "that they sacrificed" squeezed into 0.06 s, "Hey, pal." split into two 0.1 s lines) and some words were missed. The same file transcribed from the separated dialogue stem gave correct lines and timings. So for dubbing the order is separate → transcribe the stem. Phase 1 filtering keeps using the original audio; a dub run re-transcribes from the stem, and that transcript is the one dubbing uses.
- **Segments need merging for dubbing.** The transcript splits sentences at pauses ("we are" / "going to need a miracle"). A dub translated line by line sounds choppy; merge into sentences (gap under about 1 s, same speaker) before translating for dubbing.
- **Fitting:** Spanish ran about 10–30% longer than English on most lines. With a slot of the original line plus up to 1 s into the following gap, 20 of 22 lines fit untouched and two needed a 1.06x and 1.27x speed-up. A strict slot (original length only) would need rewrites for most lines, so the slot should include the gap before the next line. Rewrite-shorter is for lines still over after at most 1.3x.
- **Dependencies:** `transformers` must stay below 5 because the pinned torch is 2.2.2. Model caches must be redirected (`HF_HOME`, `TORCH_HOME` into `data/cache/`) or they land in `~/.cache`.
- **Spike 2 (English → Arabic, English subtitles):** Kokoro has no Arabic, so Piper `ar_JO-kareem-medium` (free, one male voice) and macOS `say -v Majed` (free, one male voice) were compared. Round trip (dub transcribed back with AssemblyAI and compared to the script): both come back almost word for word, with a few slips each, so both are intelligible. Fit with the same slot rule: Piper left 5 of 21 lines over their slot even at 1.3x (it speaks slowly and pauses; one 2.2 s line took 5.1 s), `say` left 2. A single voice for both speakers is a limit of the free options.
- **Spike 3 (English → Arabic, ElevenLabs free tier, `eleven_multilingual_v2`, stock voices George for speaker A and Brian for speaker B):** two distinct voices, and the best fit so far: 1 of 21 lines over its slot, nearly none sped up (Piper 5, macOS 2). Round trip: near word-for-word, except the one sentence the transcript had split in two ("we are" / "going to need a miracle"), which confirms sentences must be merged before translating. Cost: 440 credits for the clip's 440 Arabic characters (1 credit per character on this model). Free tier: 10,000 credits a month, stock voices only through the API, no voice cloning. That is about 20 clips this size a month; a whole film (tens of thousands of characters) does not fit, so a full dub needs a paid plan. Each synthesized line is cached on disk by voice, model and text, so refitting or remixing never spends credits twice.
- **Spike 4 (voice cloning, free, local: Coqui XTTS-v2, Arabic):** the ElevenLabs free plan cannot clone (instant voice cloning is paid), so cloning was tried locally. One reference sample per speaker was cut from the separated dialogue stem (9.7 s for A, 13.2 s for B). XTTS-v2 is a 1.8 GB download (into `data/cache/tts`), runs on the CPU (about 3.4 s a line; it is unreliable on Apple GPU), and its licence (Coqui Public Model License) is non-commercial, which fits private use only. Fit: 5 of 21 lines over their slot, more than ElevenLabs stock voices (1) and similar to Piper. Round trip: intelligible with a few slips (about as good as Piper and `say`, slightly behind ElevenLabs). Needs `torchaudio==2.2.2` to match torch. Whether the clones actually resemble the originals is a listening judgement, not measured.
- **Spike 5 (Cartesia `sonic-3.6`, cloned voices, Arabic, 2026-10-18):** the same two reference samples (cut from the dialogue stem) were uploaded to `POST /voices/clone` (language `en`, the language of the sample), then each Arabic line was spoken with `POST /tts/bytes` (`language: ar`). Cartesia has a native speed setting (`generation_config.speed`, 0.6–1.5), used instead of post-processing: a line is generated at normal speed first and only regenerated faster if it overruns its slot. Result: 2 of 21 lines over their slot (one by 0.3 s even at 1.14x, one at the 1.5x cap), 19 untouched; 23 requests for 495 characters. Round trip: closest to the script of all engines tried (one word slip, "يا صار" for "يا صاح", and one dropped word). Clones were created per speaker (private) and their ids cached in the spike folder; delete them from the account when a film is finished. Whether the clones resemble the original actors is a listening judgement.
- **Dialect must be chosen.** Asked for "Arabic", Claude wrote colloquial Gulf Arabic, which both voices (Modern Standard) would read oddly. Asking for "Modern Standard Arabic (Fusha)" gave proper, partly vowelled text. The translation feature needs a language-variant setting (the language code alone is not enough); for Arabic default to Fusha.
- **Not yet judged:** how the voices sound. Output for listening: `data/samples/dubbing_test.es.preview.mp4` (and `.es.m4a`). Decision after listening: keep Kokoro, or try Piper or ElevenLabs.

### 2.1 Source separation
- Demucs (local; Apple GPU via MPS or CPU) → `dialogue` and `background` stems. Background kept so only voices change. Runs once per film, cached, in the background (a film may take 10-20 min on CPU). Rented GPU only if too slow.

### 2.2 Speech synthesis (free voices first)
- TTS provider behind the interface. Free candidates, in the order to try:
  1. **Kokoro** (82M, Apache licence, runs locally, natural for its size). Languages: English, Spanish, French, Italian, Portuguese, Hindi, Japanese, Mandarin. No German, Arabic or Urdu.
  2. **Piper** (fast ONNX voices, many more languages, flatter delivery) for languages Kokoro lacks.
  3. **macOS `say`** (nothing to install, many languages, robotic): the zero-dependency baseline and a test double for the pipeline.
  4. Paid fallback: **ElevenLabs** (multilingual voices, later voice cloning).
- Per-speaker voice assignment (stored in manifest; "The cast" UI lets you rename speakers and pick voices).
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
