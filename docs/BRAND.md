# Velvet Dub — Brand Reference (for building)

Source: `Velvet-Dub-Brand-Guidelines.pdf` (v4, Oct 2026). This file is the working reference for implementation; the PDF is the visual original. If they disagree, the PDF wins — fix this file.

Tagline: **A movie palace in your living room.** Name: "Velvet Dub", two words, title case.

## Principles
1. **The velvet frames; the film performs.** Drapes/valance/seats sit at the edges. Picture, subtitles and controls stay clean.
2. **Classic, not costume.** Soft folds, fine gold trim, generous darkness. No cartoon curtains, popcorn, reels, clapperboards, spotlights, film-strip borders.
3. **Two reds, two jobs.** `velvet` = the house (buttons, sidebar, featured ticket). `signal` = a filter is acting. Never swap.
4. **Brass is jewelry.** Brass/gilt only as thin lines, bulbs, small labels. Never a fill or a button.
5. **Plain words, a little showmanship.** Plain sentences everywhere; theatre words only in headings and names.
6. **Nothing is hidden.** Every cut is shown before playback and can be undone.

## Color tokens
Dark only. No light theme.

| Token | Hex | Use |
|---|---|---|
| ground | #0F0B0B | Page/app background |
| stage-black | #070505 | Behind the screen, in the player |
| surface-deep | #140D0D | Upload zone, marquee sign, filter-timeline panel |
| panel | #1A1312 | Input fills, selected list row |
| raised | #26191A | Removable language chips (timeline tracks use #221817) |
| line | #3A2A2A | Hairline rules (decorative, not a control border) |
| border-control | #4D3838 | Inputs, selects, segmented controls, small secondary buttons |
| border-strong | #5A4444 | Outlined secondary buttons |
| ink | #F3ECE4 | Primary text/icons; ticket paper |
| ink-soft | #DCCFC4 | Long paragraphs, supporting copy |
| muted | #B3A398 | Labels, metadata, timestamps |
| faint | #93847B | Off states, axis ticks. Lowest grey allowed for text |
| velvet | #9B1B24 | Primary buttons (ivory text), featured ticket, red top rules on panels |
| velvet-deep | #5E0F15 | Fold shadows, back-row seats, sidebar dark edge |
| velvet-mid | #8A1820 | Drape folds, swags, front-row seats |
| velvet-sheen | #B8383F | Single soft drape highlight. Never a flat fill |
| velvet-shadow | #2E070B | Darkest fold, valance pelmet board |
| on-velvet | #F0D9D2 | Inactive nav/labels on the velvet sidebar |
| signal | #E5484F | Filter marks on timeline/seek bar, "Skipped 42 s", Filters heading, processing progress. Never decoration |
| brass | #D9A441 | Marquee bulbs, small uppercase labels, step lines, speaker names, poster frame |
| gilt | #C99A3E | Trim only: braid, pelmet lines, tie-back cords, double rule under wordmark |
| fringe | #B88A34 | Valance fringe, tassels |
| ticket-ink | #1A1010 | Text/buttons on ivory ticket stock |
| ticket-red | #7A1520 | "Admit" line on tickets |
| night-sky | #1B2027 | Placeholder harbor scene |
| night-sea | #131920 | Placeholder harbor scene |
| silhouette | #0D1014 | Placeholder harbor scene |
| lamp | #F3D9A4 | Lighthouse lamp |
| subtitle-second | #E9D9B4 | Second subtitle language |

Contrast: all text ≥ 4.5:1 on its ground. Never use anything greyer than `faint` for text.

```css
:root{
  --ground:#0F0B0B; --stage-black:#070505; --surface-deep:#140D0D; --panel:#1A1312;
  --raised:#26191A; --track:#221817; --line:#3A2A2A; --border-control:#4D3838; --border-strong:#5A4444;
  --ink:#F3ECE4; --ink-soft:#DCCFC4; --muted:#B3A398; --faint:#93847B;
  --velvet:#9B1B24; --velvet-deep:#5E0F15; --velvet-mid:#8A1820; --velvet-sheen:#B8383F;
  --velvet-shadow:#2E070B; --on-velvet:#F0D9D2; --signal:#E5484F;
  --brass:#D9A441; --gilt:#C99A3E; --fringe:#B88A34;
  --ticket-ink:#1A1010; --ticket-red:#7A1520; --subtitle-second:#E9D9B4;
}
```

## Typography
- **Limelight** — wordmark and headings only. One weight. Never bold, never all caps, never letter-spaced.
- **Archivo** (wdth 62–125, wght 400–800) — everything else. Use tabular figures for timecodes/numbers.
- Google Fonts: Limelight; Archivo.

| Style | Size | Use |
|---|---|---|
| display-hero | 83px | Landing hero, once |
| display-page | 54px | Screen titles |
| display-section | 45px | Sections |
| display-sub | 29px | Subsections |
| lead | 18/29 | Intros |
| body | 16/24 | UI and copy |
| small | 14.5/22 | Help, metadata |

**Marquee label:** Archivo Bold at 75% width, uppercase, 0.18em spacing, `brass`. For kickers, step lines ("Harbor Lights · step 2 of 5") and the "Admit" line. At most one per block.

## Voice and copy
Use "you" / "your family". Avoid: "users", "content", "seamless", "unlock", "AI-powered". Theatre vocabulary only in headings, section names, plan names — never in anything a person must act on (instructions, errors, settings).

| Where | Write | Not |
|---|---|---|
| Hero | Watch it in Spanish. Skip the parts you'd rather not. | Experience cinematic magic with AI. |
| Kicker | Now showing in your living room | Welcome to the show!!! |
| Processing | The projector is warming up | Processing in progress |
| Speaker naming | The cast | Speaker diarization results |
| Review | Before the curtain goes up | Review your configuration |
| Skip notice | Skipped 42 s of violence | Scene censored by our filter |
| Override | Keep it in | Override filter |
| Footer | Your seat is saved. | Thanks for visiting our website. |

- Plans: **Matinee** (free), **Family**, **Premiere**, **Schools**. Landing features: "Row A / B / C".
- Filter categories (plain): swearing, nudity, sexual content, violence, drugs and drinking, scary scenes.
- Times are runtime timestamps (`41:18`) in tabular numbers. Missing facts stay as visible placeholders like `[PRICE]`.

## Layout and components
- **Corners square**, except controls (2px radius). No rounded cards, pill buttons, drop shadows, gradient washes, emoji.
- **App:** slim velvet top bar (Limelight wordmark, gilt double rule along its lower edge; nav in `on-velvet` on the right; current page on a `velvet-shadow` inset). Page = brass step line → Limelight screen title → sections split by hairlines. Nav items today: Add a title, Library (Settings joins when it exists). See `docs/design/add-title-redesign/`, which replaced the sidebar.
- **Player:** title bar above the stage, valance over the screen, curtains at the sides, controls below a velvet rule.
- **Landing (later/optional for a private tool):** marquee sign, full-width stage, "Same film, your cut," Rows A–C, tickets, velvet-ruled footer.
- **Buttons:** primary = velvet fill, ivory text, **one per screen**. Secondary = `border-strong` outline. Text actions = underlined ivory.
- **Inputs / segmented controls:** `panel` fill, `border-control` edge, label above in `muted`. Chosen option fills `velvet`.
- **Filter timeline:** labeled lanes (e.g. Language, Sexual content, Violence, Scary scenes); each filtered moment is a block sized to its length. On the Review page each kind has its own colour, and every lane is named in words too: nudity `signal` red (#E5484F), sex scenes yellow (#E8C14A), swearing blue (#4DA3E0), violence orange (#E8853A), scary scenes violet (#A58AE0), drugs and drinking green (#6CC08B). This is a deliberate exception to "no third accent colour", for this one chart (`--cat-*` in tokens.css). Panel uses `surface-deep` with a velvet top rule.
- **Skip notice:** "Skipped 42 s" in `signal`, then the category, then two text actions ("What happened?", "Keep it in").
- **Subtitles:** ivory with soft shadow; second language in `subtitle-second`. Filtered words render as `*****`.

## Motifs (decorative — hide from screen readers)
- **Drapes:** uneven fold widths; shade smoothly velvet-shadow → velvet-mid → velvet with one narrow velvet-sheen highlight. Soft shadow at top (under valance) and bottom. Drawn back with a gilt tie-back cord and small fringe tassel ~60% down, then flares to the floor. Mirror right from left. Never hard stripes, evenly repeating folds, flat red, scallops.
- **Valance:** velvet-shadow pelmet, fine gilt line above and heavier below; soft festoon swags with two fold lines, faint sheen, gilt braid, fine fringe; gilt-edged tails at both ends.
- **Marquee:** dotted brass bulb border around the hero sign, landing only, once per page.
- **Seats:** two staggered rows (velvet-deep behind, velvet-mid front) under the landing stage only.
- **Tickets:** plans/pricing only. Ivory stock, dashed perforation, two punched notches, price sideways on the stub; the featured plan prints on velvet.

## Logo
- Mark: "VD" in Limelight, ivory, in a velvet square ringed by brass marquee bulbs. On velvet backgrounds the square drops to `velvet-deep`.
- Primary lockup: mark then wordmark, gap = ¼ mark width. Marquee lockup (64px bulbs; 32/16px solid brass line at small sizes) for landing hero/title cards only. Mark alone for app icon, favicon, sidebar, avatars. Clear space = height of the V.
- Never: put in a circle, rotate/skew, change bulb spacing, round corners, add shadows/glows, recolor letters, set "VD" in another face.
- Wordmark: Limelight, ivory on dark, `ticket-ink` on ivory; never stretched or outlined.

## Imagery and icons
- Until real frames exist: flat illustrated harbor scene (night sky, sea, cliff, lighthouse with lit lamp). No people, no gradients inside the scene. No stock photos.
- Icons: few; words first. Inline 2px stroke, 18–22px, ivory: back, play, pause, rewind 10 s, full screen. Icon-only buttons need an accessible label and a 44px hit area. No emoji.

## Accessibility
Text ≥ 4.5:1 on its ground; touch targets ≥ 44px; filters labeled, never distinguished by color alone; drapes/valances/seats `aria-hidden`.

## Don't
Hard-striped or evenly repeating curtains; scalloped valances; flat cartoon red · popcorn, reels, clapperboards, spotlights, film-strip borders · brass/gilt as fill or button; any third accent color · velvet for filter marks, or signal red for buttons · bold/all-caps/letter-spaced Limelight · theatre puns in instructions, errors, settings · bulbs/seats/tickets outside their one place · rounded cards, pill buttons, drop shadows, gradient washes, emoji.
