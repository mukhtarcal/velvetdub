# Add a title, processing and library: redesign

Design for three web screens: **Add a title**, **Processing** and **Library**. The mockups in this folder are the visual reference. This file says what to build, what each control does, and what has to change behind the screens. Where this file and the mockups disagree, this file wins. `docs/BRAND.md` still governs everything not stated here.

Live canvas (owner only): https://claude.ai/artifact/K5p4UkhNvANqv2cW3tj6fK

## The files

| File | Screen |
|---|---|
| `Main.dc.html` | Add a title |
| `Processing.dc.html` | Processing, with the curtain animation |
| `Library.dc.html` | Library |
| `canvas.json` | How the canvas lays out the three screens (not needed to build) |

The `.dc.html` files are design-canvas source, not ordinary web pages: opening one in a browser will not show the design. Read them as markup. Every color, size, spacing and line of copy is written inline. The `<script type="text/x-dc">` block at the bottom of each holds the mockup's demo logic (sample data, toggles, the fake progress timer). It shows the intended behaviour; don't port it.

## What changes, in short

1. **No sidebar.** A slim velvet bar across the top with the wordmark and two links: **Add a title** and **Library**. Nothing else in the menu for now.
2. **Add a title is the home page.** Library is the second page.
3. On Add a title, **filters and subtitles are both optional** and sit in **two separate sections**. Filters come first.
4. You choose which of **five filters** to run: Nudity, Sex scenes, Scary scenes, Violence, Swearing. **Only what you choose is processed**: with nothing chosen the film is just stored.
5. **Processing** shows a stage whose curtains stay shut while the film is processed and open when it is done.
6. **Library** cards show your choices and live status. A title still processing shows closed curtains over its picture.

## Layout shared by all screens

- **Top bar:** full width, background is the smooth velvet sheen `linear-gradient(90deg, #4A0C12 0%, #6A121A 35%, #5E0F15 65%, #3A0A0F 100%)`, with a 4px `double` gilt (`#C99A3E`) border along the bottom. Inside, a 1184px max-width row, 32px side padding, min height 76px:
  - Left: "Velvet Dub" wordmark in Limelight, 30px, ivory. It links to the home page.
  - Right: nav links, each 44px tall with 18px side padding. Inactive links are `on-velvet` (#F0D9D2). The current page is ivory on a `velvet-shadow` (#2E070B) inset and has `aria-current="page"`.
  - At phone width the row wraps, so the links drop under the wordmark.
- **Page body:** 1184px max width, centred, padding 56px top, 32px sides, 80px bottom.
- **Page header:** brass marquee label (step line or kicker), then the Limelight screen title at 54/64.
- The player stays full-screen with no top bar, as today.

## Screen 1: Add a title (`Main.dc.html`)

Step line: **"Add a title · step 1 of 2"**. Title: **"Add a title"**. A hairline (`line`) closes the header.

### Section "The film"
- Limelight subsection heading (29/36).
- Upload zone: `surface-deep` fill, 1px dashed `border-control`, 24px padding.
  - With no file: "Choose a movie or episode from your computer." in `ink-soft`, then "MP4, MOV, MKV, WebM or AVI." in `muted`. Secondary button **Choose a file**.
  - With a file: the file name in ink, then size and runtime in `muted` with tabular figures (e.g. "2.4 GB · 1:48:12"). The button becomes **Choose a different file**. Show the runtime only if it can be read in the browser; otherwise show the size alone.
- **Name** field below, label in `muted`, prefilled from the file name as today.

### Section "Filters" (optional)
- Panel: `surface-deep` fill with a 4px `velvet` top rule, the brand's filter-panel treatment. 28px padding.
- Heading **"Filters"** in Limelight, colour `signal`, as BRAND.md specifies for the Filters heading. "Optional" in `muted` at the right.
- Intro: "Choose what to skip or mute. Only what you choose is processed, and we show you every cut before you watch. You can keep any of them in."
- Five toggle tiles in a grid (3 columns on wide screens, 12px gap). Each tile is a `<button aria-pressed>` with a checkbox square, the name, a one-line hint, and a state word:

  | Tile | Category id | Hint |
  |---|---|---|
  | Nudity | `nudity` | Bare bodies, partial or full. |
  | Sex scenes | `sexual_content` | Sex scenes and sexual moments on screen. |
  | Scary scenes | `scary_scenes` | Jump scares and frightening images. |
  | Violence | `violence` | Fights, weapons, blood and injury. |
  | Swearing | `swearing` | Swearing and crude words in the dialogue. |

  Swearing is found from the words in the dialogue, not the picture, and it is always on offer (it needs no scanner). The first four are scanned in the picture and can be greyed out by the scanner.

  - Off: transparent fill, 2px `line` border, empty square (`panel` fill, `border-control` edge), state word **"Plays as is"** in `faint`.
  - On: `panel` fill, 2px `velvet` border, square filled `velvet` with an ivory 2px-stroke check, state word **"Will be skipped"** in ink (**"Will be muted"** for Swearing, since words are muted, not skipped).
  - Selection uses velvet, not signal. Signal stays reserved for a filter that is acting during playback. The state word means the state is never shown by colour alone.
  - Default: none selected.
- Footnote in `muted`: "Scenes are found by scanning the picture. Swearing is found from the words in the dialogue, so choosing it means the dialogue is transcribed. Choose nothing and the film is only stored."

### Section "Subtitles" (optional)
- Outlined box (1px `line` border, no fill), so it reads as clearly separate from the filter panel. Limelight heading **"Subtitles"** in ink, "Optional" at the right.
- Segmented control (BRAND.md style: `panel` fill, `border-control` edge, the chosen option fills `velvet`): **No subtitles** | **Add subtitles**. It is a radio group. Default: **No subtitles**.
- With "Add subtitles": the label "Languages", then the 14 language chips from `LANGUAGES` in `web/src/lib/titles.ts` (multi-select, `aria-pressed`, chosen = velvet fill). Selecting zero languages is allowed while editing, but then the hint "Choose at least one language, or pick No subtitles." appears and submit is disabled.
- With "No subtitles": "You can add subtitles later from the title page." **Open question:** there is no title page yet. Either build a way to add subtitles to a processed title, or drop this line.
- This replaces today's `LanguagePicker` rule that one language must always stay chosen.

### Section "Dubbing" (optional)
- Built the same way as Subtitles, directly under it: Limelight heading **"Dubbing"** with "Optional" at the right, and a segmented control **No dubbing** | **Add dubbing** (radio group, default **No dubbing**).
- With "Add dubbing": the label "Languages", then language chips (multi-select, `aria-pressed`, chosen = velvet fill). **Only languages the voices can speak are shown**, taken from `dub_languages` in `/api/capabilities` and ordered as in `LANGUAGES`. Selecting zero is allowed while editing, but then "Choose at least one language, or pick No dubbing." appears and submit is disabled ("Choose a dubbing language first.").
- Below the chips, in `muted`: "A dub speaks in a copy of each person's own voice, with the music and sound effects kept. It is the slowest step and uses credits with the voice service. A film is never dubbed into the language it is already in."
- **When this computer can't dub** (no voice service key, or the dubbing install is missing; `dub_languages` is empty): the control is disabled and reads "Dubbing isn't set up on this computer yet." in `ink-soft`. Nothing is shown about it until the server has answered, so it never claims dubbing is missing while still asking.
- Subtitles and dubbing are independent: the same language can be chosen for both (a dub plus subtitles in the film's own language is the common case).
- Summary gets a third row, **Dubbing:** the chosen languages ("Arabic and Spanish"), or "None". With a dub chosen, the hint beside the button reads "Next, we upload the film and start processing. The dub is the slowest part."

### Summary and submit
- Hairline above, then a two-row list:
  - **Filters:** the chosen filters joined with commas and "and" ("Nudity and swearing"), or "Nothing. The film plays as is."
  - **Subtitles:** the chosen languages ("English and Spanish"), or "None".
- Primary button **Upload and continue**, the only primary button on the screen.
  - Disabled (`velvet-deep` fill, `muted` text) when there is no file, no name, or subtitles are on with no language chosen.
  - The hint beside it says why: "Choose a file first." / "Choose a subtitle language first.". When submit is enabled it reads "Next, we upload the film and start processing." With a dub it adds "The dub is the slowest part."; with nothing chosen at all it reads "Next, we upload the film. Nothing else is processed."
- Uploading keeps today's progress bar and Cancel button.

## Screen 2: Processing (`Processing.dc.html`)

Step line: **"<title name> · step 2 of 2"**. Title: **"The projector is warming up"** while working, **"All set"** when done. The heading has `aria-live="polite"`, so a screen reader announces the change.

### The stage (decorative, `aria-hidden="true"`)
- A 16:9 box, `stage-black` background, full content width.
- **Behind the curtains:** the picture, inset 9% left and right, 15% top, 5% bottom. Use the harbor placeholder (night sky, beam, moon, sea, cliff, lighthouse with a `lamp` window) until a real frame from the film is available. A frame grabbed from the film is a later improvement.
- **Valance (on top):** a 26px `velvet-shadow` pelmet with a 1px gilt line above and a 3px gilt line below. Under it, four festoon swags (`velvet-mid`), each with a `velvet-deep` fold line, a faint `velvet-sheen` fold line at 35% opacity, a 2px gilt braid along the edge, and a dotted `fringe` line just below. The exact SVG paths are in the mockup.
- **Curtains:** two panels, left and right. Each is shaded with uneven folds and a single sheen highlight, plus a darker top and bottom. The right panel is the same gradient mirrored (`270deg`):
  ```
  background:
    linear-gradient(180deg, rgba(7,5,5,.6) 0%, rgba(7,5,5,0) 20%, rgba(7,5,5,0) 78%, rgba(7,5,5,.65) 100%),
    linear-gradient(90deg, #2E070B 0%, #8A1820 6%, #9B1B24 11%, #5E0F15 18%, #8A1820 25%, #B8383F 29%,
      #9B1B24 33%, #5E0F15 43%, #8A1820 50%, #2E070B 57%, #9B1B24 64%, #8A1820 75%, #5E0F15 83%,
      #9B1B24 91%, #5E0F15 100%);
  ```
  - **Shut (while processing):** each panel is 50.5% wide (they overlap slightly in the middle). The clip-path is a plain rectangle written with the same 9 points as the open shape, so the browser can animate between them:
    `polygon(0 0, 100% 0, 100% 22%, 100% 44%, 100% 60%, 100% 74%, 100% 90%, 100% 100%, 0 100%)`
  - **Open (done):** each panel is 17% wide. The inner edge curves in to a tie-back about 60% down, then flares to the floor:
    `polygon(0 0, 100% 0, 92% 22%, 72% 44%, 48% 60%, 64% 74%, 88% 90%, 100% 100%, 0 100%)`
    The right panel uses the mirrored points (`polygon(100% 0, 0 0, 8% 22%, 28% 44%, 52% 60%, 36% 74%, 12% 90%, 0 100%, 100% 100%)`, and its closed form likewise).
  - **Animation:** `width` and `clip-path` transition together over 2.8s, `cubic-bezier(.65,0,.25,1)`.
  - **Tie-backs:** a 3px gilt cord, 9% wide, at 60% height on each side, and a 7×22px `fringe` tassel hanging from its inner end. They fade in over 0.6s, starting 2.4s after the curtains start opening, and disappear at once if the curtains close.
  - **Reduced motion:** under `@media (prefers-reduced-motion: reduce)` there are no transitions; the curtains simply switch from shut to open.
- **Trigger:** the curtains open when the job `status` becomes `done` from the existing `/progress` polling. If the page loads for a title that is already done, show the curtains open straight away with no animation. They animate only when you watch the change happen.
- **Failed:** curtains stay shut and the existing error note and **Try again** show below, as today.

### Below the stage
- **While working:** a 6px `signal` progress bar on a `track` (#221817) background, then the six pipeline stages from `PIPELINE_STAGES` in a two-column list with hairlines between rows.
  - Each row shows the stage name and its state word: Waiting, Working, Done, or Already done for skipped.
  - The Working word is `signal`; Done is `ink-soft`; Waiting is `faint`.
  - Then: "You can leave this page. The film keeps processing and shows up in your library when it is ready."
- **When done:** a lead paragraph, e.g. "We found 14 moments to skip, 3 min 12 s in all. Look them over before you watch. You can keep any of them in." The numbers come from the review data for the current profile (count of resolved filters and `runtime_removed`).
  - Then primary **Review the cuts** and secondary **Watch now**.
  - If nothing was found: "We found nothing to skip." and **Watch now** as the primary.
- Remove the language picker and "Start processing" button that today appear when you arrive without an `autostart`. Subtitles are chosen on Add a title now.

## Screen 3: Library (`Library.dc.html`)

- Kicker **"Now showing in your living room"**, title **"Library"**, and the primary button **Add a title** on the right. **Open question:** this repeats the top-bar link; drop the button if it feels doubled.
- Grid of titles: `repeat(auto-fill, minmax(320px, 1fr))`, 40px row gap, 28px column gap. Each card has:
  - **Picture:** 16:9, in a 1px `brass` poster frame with 6px `stage-black` padding (the harbor placeholder for now). While the title is processing, closed curtains and a small valance (10px `velvet-shadow` band with a 2px gilt line) cover it. They use the same gradients as the processing stage, with no animation needed.
  - **Name** (18/26, ink), then the runtime (`muted`, tabular figures).
  - **What you chose** (`muted`): "Skips nudity and sex scenes · Subtitles in English and Spanish". With nothing chosen, use "No filters" or "No subtitles".
  - **Status:**
    - Ready: secondary **Watch** and the text action **Review the cuts**.
    - Processing: a 6px `signal` progress bar, the current stage name, and the percent.
    - Failed: "Stopped while <stage, lower case>." and the text action **Try again**.
- The Library polls progress for any title that is processing. Polling only while at least one title is processing is enough.
- **Suggestion (not yet decided):** after "Upload and continue", go to the Library instead of the processing page. The card's curtains could then open on the spot when the title finishes.

## Behind the screens

### Dubbing adds steps to Processing
- `ProcessRequest.dub_languages` (default empty). The API refuses a language the voices can't speak, and any dub when dubbing isn't set up, in plain words (HTTP 422).
- Six steps are added after "Writing subtitles": separating voices from the music, listening to the voices alone, writing the dub script, copying each speaker's voice, recording the dub, mixing the dub into the film. **They are listed on Processing, and counted in progress, only for a title that asked for a dub**; for any other title they do nothing and are not shown. A title processed before dubbing existed stays "ready".
- While a dub is made, the "You can leave this page" note adds: "The dub is the slowest part, and a whole film can take a good while."
- Library cards add "Dubbed in Arabic" to the "what you chose" line, only when there is a dub.
- The dub appears in the player's existing Audio selector as "<Language> dub".

### Subtitles become optional
- `ProcessRequest.subtitle_languages` in `api/routers/titles.py`: allow an empty list (drop `min_length=1`, default to `[]`).
- `ProcessOptions.subtitle_languages` in `pipeline/context.py`: default to `[]`. The CLI keeps `--subs` and can default to none.
- Check that `TranslateStage` and `SubtitlesStage` handle zero languages. With no outputs, make sure the runner neither loops nor fails. Its up-to-date check uses `outputs_exist`, which is true for an empty list, so it should skip.
- Transcription is no longer always on: it runs only for swearing or subtitles (see "Only what is chosen is run" below).

### Only what is chosen is run
Nothing runs by default. Each step does work only when a choice needs it, and does nothing (and needs no API key) otherwise:

| Step | Runs when |
|---|---|
| Audio extraction, transcription (AssemblyAI) | Swearing or any subtitle language is chosen. A dub alone does not need it: the dub transcribes the separated dialogue itself. |
| Picture scan (Gemini) | At least one picture filter is chosen |
| Filter timeline | Always written (empty if nothing was found or chosen); it merges the picture scan and, if Swearing is chosen, the word list |
| Translation, subtitles | A subtitle language is chosen |
| Dubbing steps | A dub language is chosen |

- The film's length and its "original" audio track are always recorded (the player and library need them); the track points at the film itself.
- `swearing_checked` is stored on the title and returned by the review data, so Review says "Not checked for swearing" instead of an empty list. A title made before this is null and reads as checked: it always was.
- Choosing more later does only the missing work: adding Swearing to a subtitled title redoes just the filter timeline; adding subtitles to a stored-only title extracts, transcribes, translates and writes them.
- Processing lists only the steps the choices make work to do (none for a stored-only title). Readiness is still judged on every recorded step, so older titles stay "ready".
- Processing says "You chose nothing to skip, so the film plays as it is." when no filter was chosen, rather than "We found nothing to skip."

### Filters choose what the picture scan looks for
- Add `filter_categories: list[FilterCategory]` to `ProcessRequest` and `ProcessOptions`.
  - Only the four picture categories are allowed from the UI: `nudity`, `sexual_content`, `scary_scenes`, `violence`.
  - The default is empty.
- **No picture categories chosen:** the visual scan does nothing. It writes an empty `visual_events`, costs nothing, and is reported as done or skipped.
- **Video-model scanner** (`SceneScanner`, Gemini): build the prompt from the chosen categories instead of the fixed list in `features/scene_filtering/prompt.py`. Keep the per-category descriptions there, in the feature, not in `providers/`.
  - `drugs_and_drinking` is in today's prompt but not offered in the UI, so it is no longer scanned for unless chosen.
  - Add the chosen categories to `config_key`, so changing them re-scans instead of reusing old clip results.
- **Frame scanner** (`FrameScanner`, OpenAI Decisions) only knows nudity and sexual content. If you choose Scary scenes or Violence while `MODERATION_PROVIDER=openai`, there are two options:
  - (a) the UI greys those tiles out with a plain note ("This scanner can't check for violence or scary scenes."), from a new field on `/api/health` or a small `/api/capabilities`; or
  - (b) the API refuses with a clear message.
  - Prefer (a). Ask only the frame questions for categories that were chosen.
- **Detection vs decision stays intact.** The stored events are still profile-independent; the choice only narrows what was looked for. Playback still applies the `FilterProfile`.
  - Record what was scanned on the manifest (e.g. `scanned_categories`), so Review and the Library can say "Not checked for violence" instead of implying nothing was there.
  - **Open question:** should these choices also become the profile's rules for this title? For example, choose Violence here and violence gets skipped even if the active profile only skips strong violence. The simplest first version: the choices decide what is scanned, and the profile decides the action. Ask before building anything more.

### Library data
- `TitleSummary` needs the chosen filters and subtitle languages (from the manifest) for the "what you chose" line. It also needs the running stage and percent; the client can get those from `/progress`.

### Navigation
- Replace the sidebar in `AppLayout.tsx` and `App.css` with the top bar.
- Routes: Add a title at `/` and Library at `/library`. Update every `Link`/`navigate` that points at `/` or `/add`; consider keeping `/add` redirecting to `/` so old links keep working.
- Profiles and Settings (plan steps 1.4 and 1.5) don't exist yet and stay out of the menu.

## Copy checklist

All copy above is final unless marked as an open question. It follows BRAND.md: plain words in anything you act on; theatre words only in headings ("The projector is warming up", "All set", "Now showing in your living room"). Sample data in the mockups (Harbor Lights 1947, the other titles, sizes, runtimes, "14 moments") is illustrative only.

## Done means

ruff, mypy (strict), pytest, and web `build`, `lint`, `test` all pass, as in `CLAUDE.md`. Add tests for:
- the empty subtitle list end to end
- a scan with no picture categories (no scanner call)
- the prompt built from chosen categories
- `config_key` changing with the chosen categories
- the Add a title rules: disabled states and summary text
- the curtains' shut and open states, including the case where the page loads already done (no animation)
