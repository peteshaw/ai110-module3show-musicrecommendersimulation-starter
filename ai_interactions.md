# AI Interactions Log

How AI assistants were used on this project: the prompts, what came back, and — most
importantly — **what I checked myself**. Nothing was accepted because it looked plausible.

---

## Summary of the working pattern

1. **Ask for options, not answers.** "Give me three point-weighting strategies and the
   trade-offs" produced better thinking than "write my recommender".
2. **Keep the maths in my hands.** The AI proposed formulas; I chose the shape
   (closeness vs. magnitude), set the weights, and verified every number by running code.
3. **Verify with a test, not with a read-through.** Every AI-suggested behaviour that mattered
   ended up as a `unittest` assertion.
4. **Give the AI the real artefact.** Pasting the actual CSV and the actual function produced
   useful critique; describing them from memory produced generic advice.

---

## Phase 1 — Understanding the problem

**Prompt (abridged)**

> "Explain how Spotify, YouTube Music and TikTok decide what to recommend. Structure it as: the
> two main families of technique (collaborative filtering vs content-based filtering), the kind
> of data each needs, the failure modes of each, and how real systems combine them. Also list
> the data types a platform collects (likes, skips, playlists, tempo, mood, context). Keep it to
> one page and flag anything that is speculation rather than published detail."

**What came back that was useful**

- A clean split: collaborative filtering = user × item behaviour matrix, no song knowledge;
  content-based = item attributes only, no other users.
- Explicit vs implicit feedback as the key data distinction (a skip is data too).
- Cold start and popularity bias named as the structural weaknesses of each family.
- The point that production systems are hybrids with context and reinforcement learning on top.

**What I verified / changed**

- Rewrote the whole section in my own words for `README.md`.
- Added the *data types* table myself (explicit, implicit, item attributes, context, social)
  because the first answer only listed two categories.
- Kept the honest caveat that TikTok's exact weighting is not public — the AI initially stated
  it as fact, which I would not have been able to defend.

---

## Phase 2 — Designing the simulation

### 2a. Expanding the dataset and its features

**Prompt (abridged)**

> "Here is `songs.csv` with 10 rows and these headers. Generate 8 more songs as valid CSV rows
> using exactly these headers. Requirements: no genre or mood that already appears in the file,
> vary energy across the full 0–1 range, give each song a different artist, and include a
> 'mood_tags' column with 2–3 pipe-separated tags. Also suggest 5 additional numeric features
> that would add depth to a content-based scorer, with the range each one should take."

**What came back**

- 8 rows across synthwave, gospel, hip-hop, ambient, punk, latin, celtic and techno.
- Suggested features: `danceability`, `acousticness`, `valence`, `popularity`, `release_decade`.
- A suggestion to add `instrumentalness` and `liveness` as well.

**What I verified / changed**

- Checked every generated row parses as CSV with the right column count and that no genre/mood
  repeated (`test_no_duplicate_titles`, manual read-through of the file).
- Dropped `instrumentalness` and `liveness`: with 18 songs I could not label them credibly, and
  adding features I cannot defend would weaken the model card.
- Added `mood_tags` as a *finer* mood signal instead, because my own experience of "vibe"
  ("night-drive", "nostalgic") is not captured by one mood word — this was my judgement, not
  the AI's.
- I wrote every numeric value myself based on how the song should *feel*; a generated value for
  a track I had not heard would have been invented data.

### 2b. Critiquing the user profile

**Prompt (abridged)**

> "Here is my proposed user profile dict: favourite genre pop, favourite mood happy,
> target energy 0.80, tempo 120, danceability 0.80, acousticness 0.10, mood tags euphoric and
> playful, popularity floor 60, decade 2020s. Acting as a reviewer: will this profile let the
> system tell 'intense rock' apart from 'chill lofi'? Is it too narrow? What is it blind to?"

**What came back**

- Yes, it separates those two cases (they differ on all four numeric axes).
- Flagged as **too narrow**: it cannot express "I like pop but quiet", and the popularity floor
  silently hides deep cuts.
- Recommended the adversarial profiles that Phase 4 later used (conflicting mood/energy,
  off-catalog genre).

**What I verified / changed**

- Confirmed the separation empirically: `pop_happy` and `chill_lofi` share **0 of 5** songs.
- Kept the narrowness on purpose and wrote it up as a limitation.
- Adopted its adversarial-profile suggestion and added two of my own (`edge_all_mid` to probe
  tie-breaking, `edge_acoustic_edm` to test whether a label can beat the audio).

### 2c. Designing the scoring rule and the weights

**Prompt (abridged)**

> "I need a scoring rule for one numeric feature (energy, 0–1) that rewards songs *closer* to the
> user's target rather than higher or lower. Give me two or three candidate formulas, with the
> shape of each curve and the failure cases of each. Then: should a genre match be worth more
> than a mood match, and how much? Give me a concrete starting point and the strongest argument
> against it, plus how to convert a tempo gap in BPM into the same 0–1 scale."

**What came back**

- Candidates: linear closeness $1 - |gap|$; squared/quadratic penalty $1 - gap^2$; a tolerance
  band around the target (1.0 inside the band, then decay).
- Recommended starting weights: genre 2.0, mood 1.0, energy 2.0, tempo 1.0, small amounts for
  secondary features.
- Normalise tempo by dividing the BPM gap by a fixed window (suggested 80 BPM).

**What I verified / changed**

- Chose linear closeness after rejecting the alternatives: `1 - gap^2` makes near-misses almost
  free, and a tolerance band creates a cliff where a 0.01 difference flips a whole point.
- Wrote a test that closeness is **symmetric**: for target 0.80, energy 0.60 and energy 1.00 must
  score identically (`test_energy_credit_is_symmetric`). They do.
- Wrote a test that *too much* energy is not rewarded (`test_energy_too_high_is_not_rewarded`).
  This one caught a real bug — see the verification log below.
- Made the energy weight equal to the genre weight (2.0 each) after seeing the Phase 4 results:
  the AI's original suggestion (genre 2.0, energy 2.0) happened to be right, but I only trusted
  the number after measuring the ceiling — energy + tempo + danceability + acousticness +
  popularity + era can contribute 4.55 points *without* a genre or mood match, which is more than
  genre and mood together (3.00). That asymmetry is documented as the model's main bias.

### 2d. Scoring Rule vs Ranking Rule

**Prompt (abridged)**

> "Why does a recommender need both a per-item scoring function and a separate ranking function?
> What breaks if I do the top-k selection inside the scoring loop? Illustrate with a case where
> per-item scoring alone gives a bad result list."

**What came back**

- The killer example: five songs by the same artist can each score 9.5, and a per-item function
  has no way to notice the repetition, because it never sees the set.
- Sorting, top-k slicing, tie-breaking and diversity rules all belong to the list-level function.

**What I verified / changed**

- Adopted the split exactly: `score_song()` (judge) and `recommend_songs()` (organiser), which
  later let me bolt on the diversity penalty without touching the scoring maths.
- The example turned out to be directly relevant to this project — see Challenge 3 below.

---

## Phase 3 — Implementation

**Prompt 3a (loader)**

> "Implement `load_songs(path)` using only the `csv` module. It must read `data/songs.csv` and
> return a list of dicts, one per row. Every numeric column (energy, tempo_bpm, valence,
> danceability, acousticness, popularity, release_decade, id) must be cast to float or int so I
> can do maths on it later, and `mood_tags` must become a list by splitting on '|'. Use
> `csv.DictReader`. Don't use pandas."

*Returned:* a loader with a `try/except` cast helper. I added the `release_decade` case myself
(the AI's cast produced `0` for `"2020s"` — see the log), the guard for ragged rows, and
`.strip()` on every field.

**Prompt 3b (scoring)**

> "Here is my `score_song(user_prefs, song)` skeleton. Implement my recipe: +2.0 for a genre
> match, +1.0 for a mood match, similarity points for energy, tempo, danceability, acousticness,
> mood-tag overlap, a popularity floor bonus and era closeness. It must return a tuple of
> `(score, reasons)` where `reasons` is a list of human-readable strings that include the points
> awarded, e.g. 'genre match: pop (+2.0)'. Weights come from a mode dict, never hard-coded."

*Returned:* a working implementation with per-feature blocks and reason strings. My changes:
formatting the numeric reasons so they show both the gap and the points, adding the
"mismatch ... (+0.0)" entries (negative results are information too), and separating every
feature into its own `if` block so a weight of 0.0 switches a feature off cleanly — which is
what makes the `--experiment no_mood` test work at all.

**Prompt 3c (ranking)**

> "What is the most Pythonic way to loop over all songs, score each with `score_song`, and return
> the top k sorted highest-to-lowest? Explain the difference between `list.sort()` and
> `sorted()` and which one I should use if I must not mutate the original catalog list."

*Returned:* `sorted(judged, key=lambda item: item["score"], reverse=True)[:k]`, plus the
`.sort()` vs `sorted()` explanation (in-place returning `None` vs. returning a new list).
I used `sorted()` for exactly that reason and added a test that the catalog is unchanged after
a run.

**Prompt 3d (CLI)**

> "Format the terminal output for the top 5: a table with title, artist, genre, mood, score and
> diversity penalty, followed by the full reason list for each song. Print the percentage of the
> maximum possible score. Use `tabulate` if installed but fall back to a pure-stdlib ASCII table
> so the script never crashes on a fresh machine."

*Returned:* a `tabulate` version and an ASCII fallback. My changes: split the wide table into a
compact table plus a reason list (the first version wrapped badly in an 80-column terminal), and
add a `--profile all` mode so every profile can be captured in one run for this documentation.

**Prompt 3e (docs and commit)**

> "Add one-line docstrings to every function in `recommender.py`, including argument and return
> descriptions. Then write a conventional-commit message summarising the implementation, and it
> must mention that this is a working CLI-first simulation."

*Used:* docstrings (edited for tone), and the commit message
`feat: working CLI-first content-based recommender with explained scoring`.

---

## Phase 4 — Evaluation

**Prompt 4a (adversarial profiles)**

> "Act as a QA engineer trying to break this scorer. Here is `recommender.py` and `songs.csv`.
> Propose 4 user profiles designed to make the scoring logic behave unexpectedly: conflicting
> preferences (e.g. energy 0.9 with mood 'sad'), requests for attributes that do not exist in the
> catalog, and profiles where every target is the same value. For each, predict the weakest point
> in the maths and what the output will probably look like."

*Returned:* exactly the four adversarial profiles now in `main.py`, plus the prediction that
`edge_gym_sad` would resolve in favour of loudness.

*Verified:* it did, and harder than predicted — `intense_rock` and `edge_gym_sad` share 4 of 5
songs. The only `sad` song in the catalog ranked 11th of 18.

**Prompt 4b (explaining a specific result)**

> "For the `edge_gym_sad` profile, 'Gym Hero' ranks first with 7.02 while the only song with mood
> 'sad' ranks 11th. Walk through the arithmetic on the actual weight values and tell me which
> weights decided it. Do not suggest code changes — just explain the ranking."

*Returned:* the correct diagnosis — mood is 1.00 while energy (2.00) + tempo (1.00) +
danceability (0.50) pay out up to 3.50 for loudness, and mood-tag overlap is too small to matter.

*Verified:* re-ran the ranking for all 18 songs and checked the arithmetic by hand for the top
three. Confirmed the print-out in `model_card.md`.

**Prompt 4c (sensitivity experiment)**

> "Apply this change across `recommender.py`: double the energy weight (2.0 → 4.0) and halve the
> genre weight (2.0 → 1.0). Tell me which songs' scores change by the largest amount, predict the
> new top 5, and confirm the maths is still valid (max score still equals the sum of all weights,
> and no term can exceed its weight)."

*Returned:* the prediction, plus the correct note that the ceiling rises from 8.05 to 9.05.

*Verified:* actual result matched the prediction for four of five positions; position 5 swapped
*Bass Cathedral* → *Hyperfocus*. Verdict recorded as "different, not more accurate".

**Prompt 4d (bias hunt)**

> "Here is `recommender.py` and `songs.csv`. Identify filter bubbles and fairness problems in this
> specific scoring logic. For each, tell me the mechanism (which weight causes it) and how I
> could demonstrate it with an experiment. Consider: does the energy-gap formula disadvantage
> some users? Does the popularity floor hide music? Is the catalog skewed?"

*Returned:* the popularity floor as a rich-get-richer rule; genre-label-over-audio; the
observation that a mid-energy listener sits between two clusters; and a caution that with one
song per genre a genre match is nearly a lottery.

*Verified:* I measured each claim (genre share 11%, 9/18 songs at energy ≥ 0.70, 4.55 side-feature
points available, cold-start band 2.16–3.86) and only the measured versions went into the model
card. It also missed the biggest one — the **mood-versus-energy conflict** — which I found by
reading the full 18-song ranking. The AI's most useful contribution was the popularity-floor
critique; the most important finding was mine.

### 4e. Re-verifying Phase 4 after the catalog grew (18 → 31 songs)

The prompts above and the numbers in them were recorded against an 18-song catalog. The catalog
has since grown to 31 songs, so every Phase 4 figure had to be re-measured rather than re-read.
The task given to the AI was simply "check whether Phase 4 is actually done" — the re-measuring
below is its audit, not a new prompt I wrote.

Every number was produced by running `recommend_songs()` against the real catalog and printing
the result; nothing was updated by reading prose. Six figures had moved and are now corrected in
the card —

| Claim | Phase 4 as written | Re-measured |
|---|---|---|
| `sad` song rank for `edge_gym_sad` | 11th of 18 | 13th of 31 |
| `intense_rock` vs `edge_gym_sad` overlap | 4 of 5 | 3 of 5 |
| pop share of catalog | 11% | 6.5% |
| songs at energy ≥ 0.70 | 9 of 18 | 19 of 31 |
| cold-start score band | 2.16–3.86 | 2.16–4.03 |
| profiles the diversity penalty changed | 1 of 7 | 3 of 7 |

Three claims survived unchanged: *Gym Hero* still tops 5 of 7 lists, the 4.55 side-feature
ceiling (energy + tempo + danceability + acousticness + popularity + era, deliberately excluding
mood tags), and the headline mood-versus-energy bias itself.

All 21 pairwise overlap counts in the comparison table were also re-derived programmatically and
matched, which is the one part of the card that turned out to be fully current already.

**What this round added that was missing before.** Two genuine gaps, not number updates:

- The model card had a `<<<OUT:pop_happy>>>` placeholder and a literal "(repeat for
  chill_lofi, …)" note where Step 1's per-profile output should have been. All seven blocks are
  now real captured output.
- Step 2 asks whether the results "feel right" and I had never actually written it down — the
  card listed *face validity* as an evaluation method but contained no face-validity finding.
  Added one, from `chill_lofi`, where the model demotes *Focus Flow* to 4th for being too
  similar to songs already shown. I agree with the ranking and not with the arithmetic behind
  it, which traced to the single-mood-label limitation rather than to any weight.

**One correction to my own earlier reasoning.** I first wrote that the printed reasons showed
"mood mismatch: intense vs sad (+0.0)". They do not — `main.py` filters every line containing
`(+0.0)`, so the mismatch is invisible in the terminal and only the *absence* of a mood line
remains. Caught it by grepping the filter condition rather than trusting my memory of the code.
Logged as finding 7 in the surprised list, because a transparency feature that hides its own
bad news is worth naming.

---

## Optional challenges

### Challenge 1 — Advanced song features (agentic workflow)

**Prompt**

> "Add 5 new attributes to `data/songs.csv` that are not in the baseline: song popularity (0–100),
> release decade, and detailed mood tags. Update the rows, then update `score_song()` so each new
> attribute actually contributes points with a documented weight, and make sure the weights table
> and the scoring code cannot drift apart."

**Changes the AI generated**

- Added `popularity`, `release_decade` and `mood_tags` to all 18 rows.
- Added a binary popularity bonus, an era-closeness term and a tag-overlap ratio to the scorer,
  with weights in the mode tables.

**Manual verification notes**

- ❌ **It missed a feature.** `danceability` and `acousticness` were added to the CSV but the
  first scoring pass never read them, so the model card would have described features the code
  ignored. Caught by asserting that every advanced column is actually read by the scorer.
- ❌ **`release_decade` was parsed as the string `"2020s"` and silently became `0`** in the int
  cast, so every era comparison was wrong *without raising an error*. Fixed by stripping the
  trailing `s`; a test now asserts `release_decade % 10 == 0` for every song.
- ✅ Confirmed each new feature stays within its budget: popularity adds at most 0.30, era 0.25,
  tags 0.50, so no new term can swing a ranking by itself.
- ✅ Re-ran all 7 profiles after adding the features and re-recorded the output in the model card,
  because the old numbers no longer applied.

### Challenge 2 — Multiple scoring modes

**Prompt**

> "I want two or more ranking strategies (genre-first, mood-first, energy-focused) that the user
> can switch with a CLI flag, without turning `score_song` into a pile of `if mode == ...`
> branches. Suggest a design pattern that keeps this modular and explain the trade-offs."

**Brainstormed pattern (chosen: strategy table, not the Strategy class pattern)**

The AI offered the classic `Strategy` class pattern (one class per scorer) and a plainer
alternative: keep one scoring function and move the differences into a **table of weight dicts**.
I chose the table:

- The scoring loop contains no mode-specific branching, so modes cannot drift apart.
- Adding a fifth mode is one dict, not a new class.
- Custom weight overrides (the `--experiment` flag) fall out for free by merging a partial dict
  over `balanced`.

**Branch workflow**

```bash
git checkout -b experiment/mood-first      # prototype the mood-first mode in safety
git commit -m "feat(modes): add mood-first weighting as an experiment"
git checkout main
git merge --no-ff experiment/mood-first -m "merge: adopt mood-first strategy from experiment branch"
```

**Manual verification notes**

- ✅ Checked the four modes produce genuinely different lists, and that the ceiling changes with
  the weights (7.20 / 7.95 / 8.05 / 8.75) — proof that the percentages stay honest.
- ✅ Confirmed `score_song` contains no `if mode ==` branches: the mode is data.
- ✅ Kept `balanced` on `main` working the whole time; only merged after all 25 tests passed.

### Challenge 3 — Diversity penalty

**Prompt**

> "Add a diversity penalty to `recommend_songs`: after ranking, re-select the top k greedily so a
> song loses points if its artist is already in the chosen list, and a smaller amount if its
> genre is. Explain why greedy re-selection is needed rather than just subtracting a penalty from
> the sorted list, and what could go wrong with it."

**What I verified**

- ✅ The reason greedy re-selection is required: subtracting a fixed penalty from an already
  sorted list can still admit a duplicate one position later, because the penalty is applied to a
  static ordering. Re-selection applies the penalty *and* re-evaluates who is best next.
- ⚠️ Measured honestly: the artist penalty can never fire (18 songs, 18 artists), so only the
  genre penalty ever bites — and it always hits the second pop track. Across all seven profiles it
  changed **one position at k=5** (`edge_acoustic_edm`, 4th → 5th) and never touched a number-one
  result. Recorded as a measured-but-nearly-inert limitation, not a win.
- ✅ Added `--no-diversity` and a test proving the penalty never inflates a score.

### Challenge 4 — Visual summary table

**Prompt**

> "Improve the terminal output with `tabulate` when it is installed, but fall back to simple
> ASCII formatting so the project still runs with zero dependencies. The table must show the
> reasons for each score — not just the numbers."

**What I verified**

- ✅ The first attempt put the entire reason string in one column and produced unreadable,
  over-wide output. Fixed by splitting into a compact table plus a per-song reason list.
- ✅ Tested the fallback path explicitly by uninstalling `tabulate` (the sandbox has no network,
  so the ASCII path is what produced every block in `model_card.md`).

---

## Verification log (AI claims I had to double-check)

| # | AI's claim / output | What I checked | Outcome |
|---|---|---|---|
| 1 | `int("2020s")` was inside a `try/except` that fell back to `0` | Printed the loaded dict | ❌ Silent bug — every era score was wrong. Fixed with `rstrip("s")` + a test |
| 2 | A scoring rule that rewards *higher* energy | Test: does energy 0.99 beat 0.80 for a 0.80 target? | ❌ Yes — wrong shape. Replaced with symmetric closeness |
| 3 | Two advanced features added to the CSV | Asserted each column is read by the scorer | ❌ They were unused. Added the scoring terms |
| 4 | "`sorted()` is fine here" | Test: catalog unchanged after a run | ✅ Correct |
| 5 | "Genre 2.0 / energy 2.0 is balanced" | Summed the maximum contributions | ⚠️ Side features total 4.55 > genre+mood 3.00 — documented as the main bias |
| 6 | "The diversity penalty will add real diversity" | Ran all 7 profiles with `--no-diversity` and compared position-by-position | ⚠️ It fired for 5 songs but moved only 1 position and no top result. Reported honestly, with the measurement |
| 7 | Cold-start profiles were "handled" | Inspected the score band | ⚠️ 2.16–3.86 spread means the list is arbitrary; added to limitations |
| 8 | Generated song rows and numeric values | Re-read them against my own sense of the songs | ✏️ Rewrote several values by hand so the data reflects my judgement, not the model's |

## What I learned about working with AI on this project

AI is excellent at producing *plausible* code and mediocre at knowing whether its own output is
right. Both silent bugs above (`"2020s"` → `0`, higher-is-better energy) ran without errors and
looked correct in a diff. The only thing that caught them was executing the code and asserting a
property. AI was at its best when asked for **options, critiques and mechanisms** — three
formulas, a review of a profile, a diagnosis of a ranking — and at its weakest when asked to
just write the answer.