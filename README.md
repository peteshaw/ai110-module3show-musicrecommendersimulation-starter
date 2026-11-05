# 🎧 VibeFinder 1.0 — Music Recommender Simulation

A small, fully explainable, **content-based** music recommender written in plain Python.
It reads a 31-song catalog from `data/songs.csv`, compares every song against a listener's
"taste profile", and prints a ranked, explained top-5 straight to the terminal.

> **Design rule for this project: no black boxes.** Every score is the sum of numbered parts,
> and every part is printed next to the recommendation. If you cannot explain why a song won,
> the recommender is not finished.

|                     |                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------- |
| **Catalog**         | 31 songs, 25 genres, 15 moods, 29 artists                                          |
| **Scored features** | genre, mood, energy, tempo, danceability, acousticness, mood tags, popularity, era |
| **Scoring modes**   | `balanced` (default), `genre_first`, `mood_first`, `energy_focused`                |
| **Extras**          | diversity penalty, explained reasons, sensitivity experiments                      |
| **Tests**           | 32 unit tests, `python -m unittest discover -s tests`                              |
| **Dependencies**    | standard library only (`tabulate` optional, for prettier tables)                   |

---

## 📁 Project structure

```
music-recommender-sim/
├── data/
│   ├── songs.csv              # the catalog: 31 songs x 13 attributes
│   └── profiles.json          # the 7 taste profiles (data, not code)
├── src/
│   ├── __init__.py
│   ├── recommender.py         # load_songs(), load_profiles(), score_song(), recommend_songs()
│   └── main.py                # CLI output (profiles loaded from data/profiles.json)
├── scripts/
│   └── compare_profiles.py    # side-by-side profile + experiment comparison
├── tests/
│   └── test_recommender.py    # 32 tests, including tests for known biases
├── model_card.md              # what the model is, how it behaves, where it fails
├── ai_interactions.md         # prompts used, what the AI produced, what I verified
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

```bash
# 1. create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS / Git Bash / WSL
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell

# 2. install dependencies (the recommender also runs with zero dependencies)
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. run the simulation
python -m src.main
```

```bash
python -m src.main                                   # default profile, balanced mode, top 5
python -m src.main --list-profiles                   # show all 7 profiles
python -m src.main --profile chill_lofi --k 3        # a different listener
python -m src.main --mode energy_focused             # a different ranking strategy
python -m src.main --no-diversity                    # turn the diversity penalty off
python -m src.main --experiment weight_shift         # Phase 4 sensitivity test
python -m src.main --profile all --k 5               # every profile in one run
python -m unittest discover -s tests -v              # run the test suite
```

### Adding a taste profile

Profiles are data, not code. They live in `data/profiles.json`, so a new listener is a JSON
edit rather than a Python edit. Copy any existing entry, change the values, and it appears in
`--list-profiles` immediately. Every key is optional — `score_song()` only reads the ones you
provide — but the numeric targets must be numbers, and the 0.0–1.0 targets must stay in range.
`load_profiles()` validates both and raises a clear error at startup if a value is wrong.

```json
"my_profile": {
  "label": "My Profile",
  "favorite_genre": "rock",
  "favorite_mood": "intense",
  "target_energy": 0.85,
  "target_tempo_bpm": 140,
  "mood_tags": ["aggressive", "gritty"],
  "min_popularity": 50,
  "target_decade": 2010
}
```

---

## 🧠 How The System Works

### 1. How real platforms actually predict your next favourite song

From what I have read, Spotify, YouTube and TikTok do not use one algorithm. They mix two families of technique:

**Collaborative filtering — "people like you also played this."**
The system builds a giant matrix of *users × items* filled with behaviour: plays, skips,
completion rates, saves, playlist adds, replays. To recommend, it finds users whose behaviour
looks like yours and serves you what they loved. It never needs to know anything about the song
itself.

- **Strength:** it can discover tastes you could never describe in words — the accidental song
  that becomes your favourite.
- **Weakness:** it has a *cold start* problem (a brand-new user or a brand-new song has no
  history to learn from), and it has a structural *popularity bias*: songs that are already
  played a lot are shown more, so they get played more. That feedback loop is how filter
  bubbles and "same five songs" radio stations happen.

**Content-based filtering — "this song looks like what you asked for."**
The system describes each song with attributes: genre, mood, tempo, energy, valence (musical
positivity), danceability, acousticness, era. It describes your taste the same way, then
measures similarity. Recommendations are the songs closest to your profile.

- **Strength:** works from day one, needs no other users, and is easy to explain and inspect.
- **Weakness:** it can only be as good as its labels. It will happily recommend a genre it
  thinks you like forever, which is a filter bubble baked into the maths.

**In practice it makes sense to use a hybrid that combines both approaches.** Production systems blend both, and layer on 
context (time of day, device, wifi vs commuting), freshness, and reinforcement-learning loops
that optimise *long-term* engagement rather than the next click. TikTok weights the implicit
"did you keep watching" signal extremely heavily, which is why a single skip changes your feed
within minutes.

**Data types involved**

| Type               | Examples                                                                   |
| ------------------ | -------------------------------------------------------------------------- |
| Explicit feedback  | likes, saves, stars, playlist adds, follows                                |
| Implicit feedback  | plays, skips, completion %, replays, dwell time, volume changes            |
| Item attributes    | genre, mood, tempo (BPM), energy, valence, danceability, acousticness, era |
| Context            | time of day, device, location, session length, shuffle vs album            |
| Social / editorial | follows, shared playlists, curated rows, editorial tiers                   |

### 2. What *my* version prioritises

VibeFinder 1.0 deliberately implements the **content-based** half only:

- **Explainability over accuracy.** Every point a song earns is printed with its reason.
- **Similarity over intensity.** "Close to what you asked for" beats "as much as possible" —
  a mellow listener should not be sent the loudest track in the catalog.
- **Genre as the strong prior, mood as the second signal.** Matching genre is worth twice a
  mood match, because genre is a coarse but reliable proxy for instrumentation and scene.
- **Partial credit everywhere else.** Tempo, danceability, acousticness, mood tags, popularity
  and era each add a small amount, so near-misses still surface.
- **No user data, no feedback loop.** This simulator never learns from what you skipped. That
  is a limitation, and it is documented rather than hidden.

### 3. The two rules: Scoring vs Ranking

These are two separate jobs, and mixing them is the most common source of confusion.

|              | Scoring Rule                                         | Ranking Rule                                          |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------- |
| **Question** | How good is *this one* song for *this one* listener? | Which songs should be shown first, and in what order? |
| **Input**    | one `user_prefs` dict + one `song` dict              | the scored list for the whole catalog                 |
| **Output**   | one number + a list of human-readable reasons        | an ordered top-*k* list                               |
| **Function** | `score_song()`                                       | `recommend_songs()`                                   |

**Why you need both.** `score_song()` is a *judge*: it can only ever look at one song, so it
cannot know that three of the songs it just praised all share the same genre.
`recommend_songs()` is the *organiser*: it can see the whole set, so it is the only place where
sorting, tie-breaking, top-*k* slicing and diversity rules belong. Keeping them separate means I
can invent a new scoring mode, or add a diversity penalty, without rewriting the other half —
which is exactly what happened in the optional challenges.

**A note on `sorted()` vs `.sort()`** — used inside `recommend_songs()`:

- `sorted(iterable)` returns a **new** list and leaves the original untouched. It works on any
  iterable, not just lists.
- `list.sort()` sorts the list **in place** and returns `None`. If you write
  `songs = songs.sort()` you will silently end up with `None` and a confusing crash later.

I use `sorted()` with `key=lambda item: item["score"], reverse=True` because the raw catalog
should stay in its original CSV order — a test (`test_scoring_does_not_mutate_the_catalog`)
guards this.

### 4. The Scoring Rule (the recipe)

**Step 1 — closeness, not size.** For any 0.0–1.0 feature, distance from the target is
converted into a similarity score:

$$\text{closeness} = 1 - \lvert \text{song}_i - \text{target}_i \rvert$$

This is symmetric on purpose: if you want energy 0.80, then 0.60 and 1.00 are equally wrong
(both +1.96 out of 2.00). A naive "higher is better" rule would reward 1.00 and punish 0.60,
which is not what "vibe" means. Tempo uses the same idea on the BPM scale:

$$\text{closeness}_{tempo} = 1 - \frac{\lvert \text{bpm}_{song} - \text{bpm}_{target} \rvert}{80}$$

Mood tags get an overlap ratio: the tags you asked for that the song actually has, divided by
the tags you asked for.

**Step 2 — weighted sum.**

$$\text{score} = \sum_i w_i \cdot \text{closeness}_i + w_{genre}\cdot \mathbb{1}[genre] + w_{mood}\cdot \mathbb{1}[mood] + w_{pop}\cdot \mathbb{1}[popularity \ge floor]$$

| Feature                | `balanced` | `genre_first` | `mood_first` | `energy_focused` |
| ---------------------- | ---------: | ------------: | -----------: | ---------------: |
| genre match            |   **2.00** |      **4.00** |         1.00 |             0.50 |
| mood match             |   **1.00** |          0.50 |     **3.00** |             0.50 |
| energy closeness       |       2.00 |          1.00 |         1.50 |         **4.00** |
| tempo closeness        |       1.00 |          0.50 |         0.75 |             1.00 |
| danceability closeness |       0.50 |          0.25 |         0.50 |             1.00 |
| acousticness closeness |       0.50 |          0.25 |         0.50 |             0.25 |
| mood-tag overlap       |       0.50 |          0.25 |         1.00 |             0.25 |
| popularity floor met   |       0.30 |          0.20 |         0.25 |             0.20 |
| era closeness          |       0.25 |          0.25 |         0.25 |             0.25 |
| **max possible**       |   **8.05** |      **7.20** |     **8.75** |         **7.95** |

**Worked example** — *Sunrise City* for the Happy Pop profile (energy 0.80, tempo 120 BPM,
danceability 0.80, acousticness 0.10, tags `euphoric|playful`, popularity floor 60, era 2020s):

| Component    | Maths                      |                Points |
| ------------ | -------------------------- | --------------------: |
| genre match  | `pop` = `pop`              |                 +2.00 |
| mood match   | `happy` = `happy`          |                 +1.00 |
| energy       | closeness 0.98 x 2.00      |                 +1.96 |
| tempo        | closeness 0.975 x 1.00     |                 +0.97 |
| danceability | closeness 0.99 x 0.50      |                 +0.49 |
| acousticness | closeness 0.98 x 0.50      |                 +0.49 |
| mood tags    | 2 of 2 tags present x 0.50 |                 +0.50 |
| popularity   | 84 >= 60                   |                 +0.30 |
| era          | 2020s = 2020s              |                 +0.25 |
| **total**    |                            | **7.97 / 8.05 (99%)** |

Every one of those rows is printed in the terminal next to the song, which is how the
recommendation can be audited by a non-programmer.

### 5. The Ranking Rule

1. **Judge every song.** Loop the catalog and call `score_song()` once per song. No song is
   skipped, so the ranking is always over the full catalog.
2. **Sort.** `sorted(..., key=score, reverse=True)`.
3. **Apply the diversity penalty (greedy re-selection).** After sorting, the top *k* are
   re-picked one at a time: at each step, every remaining candidate loses −0.75 if its
   **artist** already appears in the chosen set and −0.35 if its **genre** already appears, and
   the highest *remaining* value wins. The chosen song then stops penalising itself, so a second
   track by the same artist is still reachable — it just has to earn it.

### 6. Data flow

```
            INPUT                       PROCESS                                OUTPUT
  --------------------       ------------------------------       ------------------------
  data/songs.csv             for each song in catalog:        ranked top-k list
   title, artist,             score_song(prefs, song)          1. Sunrise City   7.94
   genre, mood,        -->      - genre  match?              2. Gym Hero       5.97
   energy, tempo_bpm,          - mood   match?          -->   3. Rooftop Lights 5.74
   danceability,               - energy closeness             + the reasons for
   acousticness,               - tempo / dance / acoustic       every point
   popularity,                   closeness
   release_decade,             - mood-tag overlap             (diversity penalty
   mood_tags                   - popularity / era               re-orders ties)
  --------------------        -> (points, reasons)
  user_prefs (dict)      -->  then: sorted() -> minus
   favorite_genre              diversity penalty
   favorite_mood
   target_energy              load_songs()       -> list[dict]      (one-time, typed)
   target_tempo_bpm           score_song()       -> judge ONE song  (Scoring Rule)
   target_danceability        recommend_songs()  -> rank ALL songs  (Ranking Rule)
   target_acousticness
   mood_tags
   min_popularity
   target_decade
  --------------------
```

### 7. Features used by `Song` and `UserProfile`

**`Song`** (one dict per CSV row, produced by `load_songs()`):

| Field             | Type            | Used how                                                                    |
| ----------------- | --------------- | --------------------------------------------------------------------------- |
| `id`              | int             | identity only                                                               |
| `title`, `artist` | str             | display; `artist` drives the diversity penalty                              |
| `genre`           | str             | categorical match, weight 2.00                                              |
| `mood`            | str             | categorical match, weight 1.00                                              |
| `energy`          | float 0–1       | closeness, weight 2.00                                                      |
| `tempo_bpm`       | int             | closeness on an 80-BPM scale, weight 1.00                                   |
| `danceability`    | float 0–1       | closeness, weight 0.50                                                      |
| `acousticness`    | float 0–1       | closeness, weight 0.50                                                      |
| `mood_tags`       | list[str]       | overlap ratio, weight 0.50 *(advanced feature)*                             |
| `popularity`      | int 0–100       | bonus if it clears the listener's floor, weight 0.30 *(advanced feature)*   |
| `release_decade`  | int (e.g. 2020) | era closeness, weight 0.25 *(advanced feature)*                             |
| `valence`         | float 0–1       | **loaded but intentionally not scored in v1** — see *Ideas for Improvement* |

**`UserProfile`** (a plain dict, so no class boilerplate is needed):

| Key                   | Meaning                                                            |
| --------------------- | ------------------------------------------------------------------ |
| `label`               | display name only, ignored by the maths                            |
| `favorite_genre`      | the genre you self-identify with (strong prior)                    |
| `favorite_mood`       | the emotional label you want                                       |
| `target_energy`       | 0.0 (ambient) → 1.0 (wall of noise)                                |
| `target_tempo_bpm`    | preferred BPM; closeness decays over an 80 BPM window              |
| `target_danceability` | how much you want to move                                          |
| `target_acousticness` | 0.0 (synthetic) → 1.0 (unplugged)                                  |
| `mood_tags`           | finer-grained wishes: `euphoric`, `calm`, `gritty`, `night-drive`… |
| `min_popularity`      | "don't show me deep cuts below this 0–100 score"                   |
| `target_decade`       | the era you are nostalgic for                                      |

Any key can be omitted and the matching term simply contributes nothing — which is how the
sensitivity experiments switch a feature off.

### 8. Biases I predicted *before* writing any code

1. **Genre is a sledgehammer.** At 2.00 points it is the single biggest term, so two songs in
   the same genre but with very different energy will still both out-rank a perfect mood match
   in another genre. Expect a filter bubble around the favourite genre.
2. **The catalog is tiny.** With 31 songs and roughly one song per genre, a "top 5" is a sixth
   of the whole library. The same few songs will recur across unrelated profiles.
3. **One mood word cannot describe a person.** Real taste is mixed ("sad but energetic"), and a
   single-label match is all-or-nothing, so conflicted profiles will behave unpredictably.
4. **The popularity floor is a rich-get-richer rule.** It systematically hides deep cuts, which
   is the same bias real platforms are criticised for.
5. **Side features add up.** Energy + tempo + danceability + acousticness + popularity + era can
   contribute up to 4.55 points *without matching the genre or mood at all* — more than the 3.00
   available from genre + mood combined. Generic loud-and-recent tracks get a head start.

Findings 1, 2 and 5 were all confirmed by experiment; the evidence is in `model_card.md`.

---

## 🖥️ Sample Recommendation Output

`python -m src.main` (default **Happy Pop** profile, `balanced` mode, top 5):

```
Loaded songs: 31
Catalog spans 25 genres and 15 moods.

==============================================================================
PROFILE: Happy Pop (default)   [pop_happy]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+----------------+-------------------+-----------+---------+-------+---------+
| # | title          | artist            | genre     | mood    | score | div.pen |
+---+----------------+-------------------+-----------+---------+-------+---------+
| 1 | Sunrise City   | Neon Echo         | pop       | happy   | 7.94  | -       |
| 2 | Gym Hero       | Max Pulse         | pop       | intense | 6.33  | -0.35   |
| 3 | Rooftop Lights | Indigo Parade     | indie pop | happy   | 5.74  | -       |
| 4 | Velvet Horizon | The Midnight Echo | edm       | happy   | 5.69  | -       |
| 5 | Salsa del Sol  | Marisol Vega      | latin     | playful | 4.64  | -       |
+---+----------------+-------------------+-----------+---------+-------+---------+

Why each song was chosen:
  1. Sunrise City — Neon Echo (pop/happy)  score 7.94 = 99% of max
       - genre match: pop (+2.0)
       - mood match: happy (+1.0)
       - energy 0.82 vs target 0.80 closeness 0.98 -> +1.96 pts
       - tempo 118 vs target 120 -> closeness 0.97 (+0.97)
       - danceability closeness 0.99 (+0.49)
       - acousticness closeness 0.92 (+0.46)
       - mood tag overlap [euphoric, playful] 1.00 (+0.50)
       - popularity 78 meets floor 60 (+0.3)
       - era 2020s vs target 2020s (same era, +0.25)
  2. Gym Hero — Max Pulse (pop/intense)  score 6.33 = 74% of max  (diversity -0.35)
       - genre match: pop (+2.0)
       - energy 0.93 vs target 0.80 closeness 0.87 -> +1.74 pts
       - tempo 132 vs target 120 -> closeness 0.85 (+0.85)
       - danceability closeness 0.92 (+0.46)
       - acousticness closeness 0.95 (+0.47)
       - mood tag overlap [euphoric] 0.50 (+0.25)
       - popularity 81 meets floor 60 (+0.3)
       - era 2020s vs target 2020s (same era, +0.25)
  3. Rooftop Lights — Indigo Parade (indie pop/happy)  score 5.74 = 71% of max
       - mood match: happy (+1.0)
       - energy 0.76 vs target 0.80 closeness 0.96 -> +1.92 pts
       - tempo 124 vs target 120 -> closeness 0.95 (+0.95)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 0.75 (+0.38)
       - mood tag overlap [euphoric, playful] 1.00 (+0.50)
       - popularity 62 meets floor 60 (+0.3)
       - era 2010s vs target 2020s (1 decade apart, +0.21)
  4. Velvet Horizon — The Midnight Echo (edm/happy)  score 5.69 = 71% of max
       - mood match: happy (+1.0)
       - energy 0.78 vs target 0.80 closeness 0.98 -> +1.96 pts
       - tempo 120 vs target 120 -> closeness 1.00 (+1.00)
       - danceability closeness 1.00 (+0.50)
       - acousticness closeness 0.95 (+0.47)
       - mood tag overlap [euphoric] 0.50 (+0.25)
       - popularity 70 meets floor 60 (+0.3)
       - era 2010s vs target 2020s (1 decade apart, +0.21)
  5. Salsa del Sol — Marisol Vega (latin/playful)  score 4.64 = 58% of max
       - energy 0.82 vs target 0.80 closeness 0.98 -> +1.96 pts
       - tempo 100 vs target 120 -> closeness 0.75 (+0.75)
       - danceability closeness 0.92 (+0.46)
       - acousticness closeness 0.85 (+0.42)
       - mood tag overlap [euphoric, playful] 1.00 (+0.50)
       - popularity 69 meets floor 60 (+0.3)
       - era 2020s vs target 2020s (same era, +0.25)

Done. Re-run with --mode energy_focused or --no-diversity to compare strategies.
```

The top result matches what I would expect for a pop/happy profile, and the reason list explains
*why* every point was awarded.

---

## 🔬 Evaluation in one screen

Seven profiles were tested (three realistic, four adversarial) plus two sensitivity experiments,
and every profile was re-run with the diversity penalty on and off. Full analysis is in
[`model_card.md`](model_card.md).

| Profile                  | Top song        | Score / max | 2nd                   | 3rd                          |
| ------------------------ | --------------- | ----------: | --------------------- | ---------------------------- |
| Happy Pop                | Sunrise City    | 7.94 / 8.05 | Gym Hero 5.97         | Rooftop Lights 5.74          |
| Chill Lofi               | Library Rain    | 7.57 / 8.05 | Midnight Coding 7.13  | Spacewalk Thoughts 5.49      |
| Deep Intense Rock        | Storm Runner    | 7.77 / 8.05 | Devil's Backbeat 5.53 | Wildfire Season 5.45         |
| EDGE: sad + high energy  | Gym Hero        | 6.47 / 8.05 | Sunrise City 5.46     | Thunder on Fifth Street 4.32 |
| EDGE: EDM + acoustic     | Velvet Horizon  | 5.64 / 8.05 | Gym Hero 4.03         | Library Rain 3.97            |
| EDGE: off-catalog genre  | Midnight Coding | 4.03 / 8.05 | Slow Collapse 3.96    | Quiet Machines 3.86          |
| EDGE: all targets at 0.5 | Sunrise City    | 6.46 / 8.05 | Rooftop Lights 4.62   | Gym Hero 4.61                |

**Headlines**

- **The profiles genuinely separate.** Happy Pop and Chill Lofi share **0 of 5** songs, so the rule
  really does tell "intense rock" apart from "chill lofi".
- **`Gym Hero` appears in 5 of the 7 lists.** It is pop, energy 0.93, 128 BPM, danceability 0.88,
  popularity 91 and from the 2020s, so it harvests almost every side-feature point even when the
  listener asked for something else. Genre + mood can supply 3.00 points; the side features can
  supply **4.55 points with no genre or mood match at all**. That asymmetry is the model's core bias.
- **A sad, high-energy listener gets hype music.** The only `sad` song in the catalog places
  **13th of 31**, outvoted by the energy / tempo / danceability cluster.
- **The genre label beats the actual sound.** The "EDM but acoustic" listener (acousticness 0.90)
  gets *Velvet Horizon*, whose acousticness is 0.15 — the exact opposite of the request. The
  genre term pays 2.00 points while getting acousticness completely wrong costs at most 0.50,
  so the label wins four-to-one over the audio.
- **Cold start degrades gracefully but has no signal.** With a genre and mood absent from the
  catalog, all 31 scores compress into a 2.16–4.03 band and the "top 5" is essentially arbitrary.
- **The diversity penalty works, but it is nearly inert on this catalog.** Only five genres hold
  more than one song (`lofi` ×3, `pop`, `ambient`, `synthwave`, `alternative rock` ×2), so the
  genre penalty rarely fires; the artist penalty fires only for the two artists with two songs
  (`Neon Echo`, `LoRoom`). It changed one position across the whole study and never touched a
  number-one result.

---

## 🎁 Optional challenges completed

| Challenge                     | Status                                                                                              | Where                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| **1. Advanced song features** | ✅ 5 added: `danceability`, `acousticness`, `popularity`, `release_decade`, `mood_tags` — all scored | `data/songs.csv`, `src/recommender.py`       |
| **2. Multiple scoring modes** | ✅ 4 modes via a strategy table, switchable with `--mode`                                            | `SCORING_MODES` in `src/recommender.py`      |
| **3. Diversity penalty**      | ✅ Greedy artist/genre penalty; `--no-diversity` to compare                                          | `_diversity_penalty()`, `recommend_songs()`  |
| **4. Visual summary table**   | ✅ `tabulate` when installed, ASCII fallback otherwise, plus a per-song reason list                  | `format_recommendations()`, `_ascii_table()` |

On **Challenge 2**, the design pattern is deliberately the simplest one that keeps the code
modular: a *strategy table* (a dict of weight dicts) rather than a class hierarchy. Adding a
fifth strategy means adding one dict — no branching inside `score_song()`. Because the scoring
loop never contains an `if mode == ...`, there is no risk of two modes drifting apart.

---

## ✅ Tests

```bash
python -m unittest discover -s tests -v     # 32 tests, ~0.01s
```

The suite covers loading and type-casting, the scoring maths (including the symmetry of
closeness and the "too much energy is not better" rule), ranking behaviour, and — deliberately
— **tests that lock in the known biases**, e.g. `test_mood_can_be_outvoted_by_the_energy_cluster`.
If someone later fixes that bias, the test fails and forces the model card to be updated.

---

## 🤖 AI usage note

AI assistants were used as a sounding board: to compare collaborative vs content-based
filtering, to critique the scoring recipe, to review the loop/sort implementation, and to hunt
for biases I had not thought of. The recorded prompts, what the AI produced, and my own
verification notes are in [`ai_interactions.md`](ai_interactions.md).

> **Note about the catalog.** The starter rows in `data/songs.csv` were reconstructed for this
> simulation (18 songs total, including a `Gym Hero` pop track). Twelve alternative/rock songs
> (ids 19–31) were later appended to widen the catalog to 31 songs; the code itself is
> data-driven and needs no changes.

---

## 🔭 What I would build next

1. **Learn the weights from behaviour** instead of hand-setting them — collect skips and
   completions and fit the weights (this is the switch from content-based to hybrid).
2. **Diversify by embedding, not by label** — cluster songs on audio features so "sounds alike"
   can cross genre boundaries.
3. **Represent mood as a distribution** rather than one word, so "sad but energetic" is
   expressible.
4. **Report uncertainty.** When the best score is low (the cold-start case), the UI should say
   "I'm not confident" instead of confidently returning an arbitrary list.

See `model_card.md` for the full list.