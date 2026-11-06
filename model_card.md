# Model Card — VibeFinder 1.0

*Last updated: November 2026. This card documents a classroom simulation, not a production
service.*

---

## Model Name

**VibeFinder 1.0** — a weighted-score, content-based music recommender that runs in the
terminal.

## Goal / Task

VibeFinder takes one listener's stated taste (a favourite genre, a favourite mood, and target
values for energy, tempo, danceability, acousticness, era and popularity) and answers one
question:

> *Out of the 31 songs in this catalog, which 5 are most likely to be liked by this listener,
> and why?*

It is a **ranking** task, not a prediction of a rating. The output is an ordered list plus a
reason sentence for every point awarded, so a human can audit the result.

The system is deliberately not trying to predict what you will listen to tomorrow, what will
go viral, or what your friends would like. It only compares a static profile against a static
catalog of songs.

## Data Used

| | |
|---|---|
| **File** | `data/songs.csv` |
| **Size** | 31 songs, one row per song |
| **Artists** | 29 (`Neon Echo` and `LoRoom` each have two songs) |
| **Genres** | 25 — `lofi` has three songs; `pop`, `ambient`, `synthwave` and `alternative rock` have two each |
| **Moods** | 15 distinct labels (`happy`, `chill`, `intense`, `sad`, `euphoric`, `angry`, `dark`, `focused`, …) |
| **Source** | 10 starter rows from the course repo, plus 8 songs written for this project to widen genre coverage (synthwave, gospel, hip-hop, ambient, punk, latin, celtic, techno), plus 12 alternative/rock songs (ids 19–30) and one `edm` song (id 31) |

**Features on every song**

- Categorical: `genre`, `mood`, `mood_tags` (fine-grained tags such as `nostalgic`, `gritty`, `night-drive`)
- Numeric 0.0–1.0: `energy`, `valence`, `danceability`, `acousticness`
- Numeric other: `tempo_bpm` (60–168), `popularity` (0–100), `release_decade` (1990–2020)

**Known limits of the data**

1. **31 songs is tiny.** A "top 5" is 16% of the entire library, so recommendations repeat.
2. **The labels are hand-written, not measured.** Real platforms get `energy`/`valence` from
   audio analysis; here they are my own estimates, so they encode my taste. Two people would
   label the same song differently.
3. **One genre and one mood per song.** A track that is genuinely "sad but energetic" or
   "folk-hip-hop" cannot be represented, so the model must choose a single label and lose the
   rest.
4. **Genre is unbalanced by nature.** With ~1 song per genre, a genre match is often a lottery
   worth 25% of the maximum score.
5. **`valence` is loaded but never scored in v1.** It is visible in the data but unused by the
   maths — a deliberate v1 choice, not an oversight.
6. **No user data at all.** There are no plays, skips, likes or playlists anywhere in this
   project, so nothing can be learned from real behaviour.

## Algorithm Summary

*(Plain language. No code.)*

Every song is scored against the profile, one feature at a time, and the points are added up.

- **Genre match: +2.00.** The biggest single reward. If the song's genre is the listener's
  favourite genre, it gets two points immediately.
- **Mood match: +1.00.** A matching mood word is worth half a genre match.
- **Energy: up to +2.00.** Instead of rewarding loud songs, the model rewards *closeness*.
  If you want energy 0.80 and the song is 0.78, it earns 98% of those two points. If the song is
  0.10 or 1.00, it earns almost nothing. Being too intense is penalised exactly as much as
  being too calm.
- **Tempo: up to +1.00,** using the same closeness idea, with the penalty spread over an 80 BPM
  window (so 118 BPM against a 120 BPM target is almost a perfect match).
- **Danceability and acousticness: up to +0.50 each,** again by closeness.
- **Mood tags: up to +0.50,** in proportion to how many of the listener's requested tags the
  song actually carries.
- **Popularity: +0.30** if the song clears the listener's minimum popularity floor (a simple
  yes/no bonus, so the model never punishes a song for being *too* popular).
- **Era: up to +0.25** for being in the listener's preferred decade.

The maximum possible score is 8.05, so the final score can be read as a match percentage.
The 5 highest-scoring songs are shown, with two twists: everything is sorted from highest to
lowest, and a song that repeats an artist or genre already in the list loses 0.75 or 0.35
points (a "diversity penalty") so the same sound does not fill the whole list.

Four alternative weightings ship with the model — `balanced`, `genre_first`, `mood_first` and
`energy_focused` — which change only the numbers above, never the structure.

> **In plain terms:** this is a checklist with fixed prices. Genre is the most expensive item on
> the list, energy is the second, and everything else is small change.

---

## Observed Behavior / Biases (Limitations and Bias)

### The headline weakness

**This system quietly ignores the mood you asked for whenever your energy request is strong.**
The clearest evidence is the adversarial "sad but high energy" listener: the only genuinely
`sad` song in the catalog (*Paper Lungs*) finished **13th out of 31**, behind twelve brighter,
louder tracks, because a mood match is worth 1.00 point while energy, tempo and
danceability together hand out up to 3.50 points for being loud, fast and danceable. In
effect, a listener who says "I want sad music, but keep it intense" gets a gym playlist with no
emotional match at all, and the printed reasons still look perfectly reasonable — which is
exactly how a bias hides in a system that *feels* transparent.

### Other patterns worth naming

**1. Generic loud-and-recent tracks have a free head start.** Genre and mood can supply at most
3.00 of the 8.05 available points. The remaining **4.55 points are reachable without matching
the listener's genre or mood at all** — energy, tempo, danceability, acousticness, popularity and
recency all pay out regardless. A track like *Gym Hero* (pop, energy 0.93, 128 BPM,
danceability 0.88, popularity 91, 2020s) therefore appears in **5 of the 7 top-5 lists**,
including profiles that asked for sad, acoustic or ambient music. This is a filter bubble
created by the *shape of the maths*, not by a genre being over-represented in the data — the
catalog is only 6% pop.

**2. The genre label beats the actual sound.** For the "EDM but acoustic" listener,
*Velvet Horizon* ranked first despite an acousticness of 0.15 against a target of 0.90 — the
near-exact opposite of what was requested. Getting acousticness completely wrong can cost at
most 0.50 points, while the genre label pays 2.00, so the tag wins four-to-one over the audio.

**3. The popularity floor is a rich-get-richer rule.** Songs below the listener's popularity
threshold earn nothing from that term, so obscure music is systematically pushed down. Real
platforms are criticised for exactly this pattern, and it is built into v1 on purpose.

**4. Cold start has no way to say "I don't know."** When the requested genre and mood do not
exist in the catalog, every song scores between 2.16 and 4.03 and the "top 5" is essentially
arbitrary. The model returns a confident-looking list of mediocre matches rather than admitting
low confidence.

**5. The diversity penalty rarely fires in this catalog.** The artist penalty only bites for the
two artists with two songs (`Neon Echo`, `LoRoom`). The genre penalty only bites when two songs
share a genre, and only five genres here hold more than one song (`lofi` ×3; `pop`, `ambient`,
`synthwave`, `alternative rock` ×2). It changed the top 5 for **three of seven profiles**
(`chill_lofi`, `edge_off_catalog`, `edge_all_mid`) and changed nothing at all for the other four.

**6. No feedback and no fairness audit.** The system cannot learn from skips, and nothing in it
protects smaller artists, languages, or niche genres beyond the weak diversity penalty. If this
were deployed, the same handful of songs would be served forever.

### Who is poorly served

Listeners whose taste is *defined by mood rather than genre* (sad, melancholic, nostalgic),
listeners who want **mid-energy** music (both loud and quiet songs are far from a 0.5 target,
and 19 of the 31 songs sit above 0.70 energy), listeners who like music that has not been
popular, and anyone whose favourite genre has exactly one song in the catalog — which is 20 of
the 25 genres here.

---

## Evaluation Process

### How I evaluated without ground truth

The honest problem with this project is that there is **no ground truth**: nobody labelled a
"correct" top 5 for each profile, and there are no real listener logs to check against. So
instead of measuring accuracy, I evaluated four other things:

1. **Face validity** — do the recommendations match musical intuition for a clearly defined
   listener, and can I justify the top result by hand?
2. **Separation** — do *different* profiles actually receive *different* songs, or does one song
   top every list?
3. **Robustness** — do the automated tests hold the invariants (score never exceeds the ceiling,
   closeness is symmetric, the catalog is never mutated)?
4. **Sensitivity** — if I change one weight, does the output change in the direction I
   predicted, or does it move randomly?

### Profiles tested

| Profile | What it represents | Why I chose it |
|---|---|---|
| `pop_happy` | Happy Pop (default) | The sanity check: a mainstream listener with a well-populated genre |
| `chill_lofi` | Chill Lofi / study music | The exact opposite of `pop_happy` on every axis — a separation test |
| `intense_rock` | Deep intense rock | Tests a genre with only one song in the catalog |
| `edge_gym_sad` | mood `sad` + energy 0.92 | Adversarial: internally contradictory |
| `edge_acoustic_edm` | genre `edm` + acousticness 0.90 | Adversarial: label contradicts texture |
| `edge_off_catalog` | genre `vaporwave`, mood `dreamy` | Adversarial: cold start, zero possible matches |
| `edge_all_mid` | every target dead-centre at 0.50 | Adversarial: tests which feature breaks ties |

### Terminal output for every profile

Each block is real captured output of `python -m src.main --profile <name> --k 5` (`balanced`
mode, diversity penalty on), trimmed to the ranked table plus the reason list for the top two
songs.

#### 1. `pop_happy` — Happy Pop (default)

```
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
```
#### 2. `chill_lofi` — Chill Lofi / Study

```
==============================================================================
PROFILE: Chill Lofi / Study   [chill_lofi]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+---------------------+----------------+---------+---------+-------+---------+
| # | title               | artist         | genre   | mood    | score | div.pen |
+---+---------------------+----------------+---------+---------+-------+---------+
| 1 | Library Rain        | Paper Lanterns | lofi    | chill   | 7.57  | -       |
| 2 | Midnight Coding     | LoRoom         | lofi    | chill   | 7.48  | -0.35   |
| 3 | Spacewalk Thoughts  | Orbit Bloom    | ambient | chill   | 5.49  | -       |
| 4 | Focus Flow          | LoRoom         | lofi    | focused | 6.55  | -1.10   |
| 5 | Coffee Shop Stories | Slow Stereo    | jazz    | relaxed | 4.35  | -       |
+---+---------------------+----------------+---------+---------+-------+---------+

Why each song was chosen:
  1. Library Rain — Paper Lanterns (lofi/chill)  score 7.57 = 94% of max
       - genre match: lofi (+2.0)
       - mood match: chill (+1.0)
       - energy 0.35 vs target 0.22 closeness 0.87 -> +1.74 pts
       - tempo 72 vs target 85 -> closeness 0.84 (+0.84)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 0.99 (+0.49)
       - mood tag overlap [calm, focused] 1.00 (+0.50)
       - popularity 65 meets floor 40 (+0.3)
       - era 2020s vs target 2010s (1 decade apart, +0.21)
  2. Midnight Coding — LoRoom (lofi/chill)  score 7.48 = 89% of max  (diversity -0.35)
       - genre match: lofi (+2.0)
       - mood match: chill (+1.0)
       - energy 0.42 vs target 0.22 closeness 0.80 -> +1.60 pts
       - tempo 78 vs target 85 -> closeness 0.91 (+0.91)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 0.86 (+0.43)
       - mood tag overlap [calm, focused] 1.00 (+0.50)
       - popularity 71 meets floor 40 (+0.3)
       - era 2010s vs target 2010s (same era, +0.25)
```
#### 3. `intense_rock` — Deep Intense Rock

```
==============================================================================
PROFILE: Deep Intense Rock   [intense_rock]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+-------------------+------------------+------------------+---------+-------+---------+
| # | title             | artist           | genre            | mood    | score | div.pen |
+---+-------------------+------------------+------------------+---------+-------+---------+
| 1 | Storm Runner      | Voltline         | rock             | intense | 7.77  | -       |
| 2 | Devil's Backbeat  | Moonshine Riot   | blues rock       | intense | 5.53  | -       |
| 3 | Wildfire Season   | Canyon Riot      | garage rock      | intense | 5.45  | -       |
| 4 | Gym Hero          | Max Pulse        | pop              | intense | 5.13  | -       |
| 5 | Paper Cut Skyline | The Hollow Coast | alternative rock | angry   | 4.86  | -       |
+---+-------------------+------------------+------------------+---------+-------+---------+

Why each song was chosen:
  1. Storm Runner — Voltline (rock/intense)  score 7.77 = 97% of max
       - genre match: rock (+2.0)
       - mood match: intense (+1.0)
       - energy 0.91 vs target 0.90 closeness 0.99 -> +1.98 pts
       - tempo 152 vs target 140 -> closeness 0.85 (+0.85)
       - danceability closeness 0.89 (+0.45)
       - acousticness closeness 0.98 (+0.49)
       - mood tag overlap [aggressive, gritty] 1.00 (+0.50)
       - popularity 70 meets floor 50 (+0.3)
       - era 2010s vs target 2000s (1 decade apart, +0.21)
  2. Devil's Backbeat — Moonshine Riot (blues rock/intense)  score 5.53 = 69% of max
       - mood match: intense (+1.0)
       - energy 0.87 vs target 0.90 closeness 0.97 -> +1.94 pts
       - tempo 132 vs target 140 -> closeness 0.90 (+0.90)
       - danceability closeness 0.89 (+0.45)
       - acousticness closeness 0.97 (+0.48)
       - mood tag overlap [gritty] 0.50 (+0.25)
       - popularity 60 meets floor 50 (+0.3)
       - era 2010s vs target 2000s (1 decade apart, +0.21)
```
#### 4. `edge_gym_sad` — EDGE: high energy but sad mood (conflicting)

```
==============================================================================
PROFILE: EDGE: high energy but sad mood (conflicting)   [edge_gym_sad]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+-------------------------+------------------+------------------+-----------+-------+---------+
| # | title                   | artist           | genre            | mood      | score | div.pen |
+---+-------------------------+------------------+------------------+-----------+-------+---------+
| 1 | Gym Hero                | Max Pulse        | pop              | intense   | 6.47  | -       |
| 2 | Sunrise City            | Neon Echo        | pop              | happy     | 5.80  | -0.35   |
| 3 | Thunder on Fifth Street | Blacktop Saints  | hard rock        | confident | 4.32  | -       |
| 4 | Storm Runner            | Voltline         | rock             | intense   | 4.24  | -       |
| 5 | Paper Cut Skyline       | The Hollow Coast | alternative rock | angry     | 4.24  | -       |
+---+-------------------------+------------------+------------------+-----------+-------+---------+

Why each song was chosen:
  1. Gym Hero — Max Pulse (pop/intense)  score 6.47 = 80% of max
       - genre match: pop (+2.0)
       - energy 0.93 vs target 0.92 closeness 0.99 -> +1.98 pts
       - tempo 132 vs target 128 -> closeness 0.95 (+0.95)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 1.00 (+0.50)
       - mood tag overlap [none] 0.00 (+0.00)
       - popularity 81 meets floor 80 (+0.3)
       - era 2020s vs target 2020s (same era, +0.25)
  2. Sunrise City — Neon Echo (pop/happy)  score 5.80 = 68% of max  (diversity -0.35)
       - genre match: pop (+2.0)
       - energy 0.82 vs target 0.92 closeness 0.90 -> +1.80 pts
       - tempo 118 vs target 128 -> closeness 0.88 (+0.88)
       - danceability closeness 0.89 (+0.45)
       - acousticness closeness 0.87 (+0.43)
       - mood tag overlap [none] 0.00 (+0.00)
       - era 2020s vs target 2020s (same era, +0.25)
```
#### 5. `edge_acoustic_edm` — EDGE: EDM genre but acoustic/mellow (conflicting)

```
==============================================================================
PROFILE: EDGE: EDM genre but acoustic/mellow (conflicting)   [edge_acoustic_edm]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+------------------+-------------------+------------+---------+-------+---------+
| # | title            | artist            | genre      | mood    | score | div.pen |
+---+------------------+-------------------+------------+---------+-------+---------+
| 1 | Velvet Horizon   | The Midnight Echo | edm        | happy   | 5.64  | -       |
| 2 | Gym Hero         | Max Pulse         | pop        | intense | 4.03  | -       |
| 3 | Library Rain     | Paper Lanterns    | lofi       | chill   | 3.97  | -       |
| 4 | Hyperfocus       | Null Signal       | techno     | focused | 3.82  | -       |
| 5 | Devil's Backbeat | Moonshine Riot    | blues rock | intense | 3.78  | -       |
+---+------------------+-------------------+------------+---------+-------+---------+

Why each song was chosen:
  1. Velvet Horizon — The Midnight Echo (edm/happy)  score 5.64 = 70% of max
       - genre match: edm (+2.0)
       - energy 0.78 vs target 0.95 closeness 0.83 -> +1.66 pts
       - tempo 120 vs target 128 -> closeness 0.90 (+0.90)
       - danceability closeness 0.90 (+0.45)
       - acousticness closeness 0.25 (+0.12)
       - mood tag overlap [none] 0.00 (+0.00)
       - popularity 70 meets floor 30 (+0.3)
       - era 2010s vs target 2020s (1 decade apart, +0.21)
  2. Gym Hero — Max Pulse (pop/intense)  score 4.03 = 50% of max
       - energy 0.93 vs target 0.95 closeness 0.98 -> +1.96 pts
       - tempo 132 vs target 128 -> closeness 0.95 (+0.95)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 0.15 (+0.08)
       - mood tag overlap [none] 0.00 (+0.00)
       - popularity 81 meets floor 30 (+0.3)
       - era 2020s vs target 2020s (same era, +0.25)
```
#### 6. `edge_off_catalog` — EDGE: genre/mood absent from the catalog (cold start)

```
==============================================================================
PROFILE: EDGE: genre/mood that do not exist in the catalog (cold start)   [edge_off_catalog]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+-----------------+-----------------+------------------+---------+-------+---------+
| # | title           | artist          | genre            | mood    | score | div.pen |
+---+-----------------+-----------------+------------------+---------+-------+---------+
| 1 | Midnight Coding | LoRoom          | lofi             | chill   | 4.03  | -       |
| 2 | Slow Collapse   | Marble Youth    | shoegaze         | wistful | 3.96  | -       |
| 3 | Quiet Machines  | Glass Cathedral | alternative rock | calm    | 3.86  | -       |
| 4 | Paper Lungs     | Ash and Ember   | emo              | sad     | 3.84  | -       |
| 5 | Chrome Requiem  | Synth Wraith    | synthwave        | dark    | 3.77  | -       |
+---+-----------------+-----------------+------------------+---------+-------+---------+

Why each song was chosen:
  1. Midnight Coding — LoRoom (lofi/chill)  score 4.03 = 50% of max
       - energy 0.42 vs target 0.50 closeness 0.92 -> +1.84 pts
       - tempo 78 vs target 100 -> closeness 0.72 (+0.72)
       - danceability closeness 0.88 (+0.44)
       - acousticness closeness 0.79 (+0.40)
       - mood tag overlap [night-drive] 1.00 (+0.50)
       - era 2010s vs target 1980s (3 decades apart, +0.12)
  2. Slow Collapse — Marble Youth (shoegaze/wistful)  score 3.96 = 49% of max
       - energy 0.52 vs target 0.50 closeness 0.98 -> +1.96 pts
       - tempo 104 vs target 100 -> closeness 0.95 (+0.95)
       - danceability closeness 0.98 (+0.49)
       - acousticness closeness 0.88 (+0.44)
       - mood tag overlap [none] 0.00 (+0.00)
       - era 2010s vs target 1980s (3 decades apart, +0.12)
```
#### 7. `edge_all_mid` — EDGE: every target dead-centre

```
==============================================================================
PROFILE: EDGE: every target dead-center (does the energy weight break ties?)   [edge_all_mid]
MODE: balanced  |  top 5 of 31 songs  |  diversity penalty: ON  |  max possible raw score: 8.05
==============================================================================
+---+----------------+-------------------+-----------+---------+-------+---------+
| # | title          | artist            | genre     | mood    | score | div.pen |
+---+----------------+-------------------+-----------+---------+-------+---------+
| 1 | Sunrise City   | Neon Echo         | pop       | happy   | 6.46  | -       |
| 2 | Rooftop Lights | Indigo Parade     | indie pop | happy   | 4.62  | -       |
| 3 | Gym Hero       | Max Pulse         | pop       | intense | 4.96  | -0.35   |
| 4 | Velvet Horizon | The Midnight Echo | edm       | happy   | 4.54  | -       |
| 5 | Slow Collapse  | Marble Youth      | shoegaze  | wistful | 4.07  | -       |
+---+----------------+-------------------+-----------+---------+-------+---------+

Why each song was chosen:
  1. Sunrise City — Neon Echo (pop/happy)  score 6.46 = 80% of max
       - genre match: pop (+2.0)
       - mood match: happy (+1.0)
       - energy 0.82 vs target 0.50 closeness 0.68 -> +1.36 pts
       - tempo 118 vs target 110 -> closeness 0.90 (+0.90)
       - danceability closeness 0.71 (+0.35)
       - acousticness closeness 0.68 (+0.34)
       - popularity 78 meets floor 50 (+0.3)
       - era 2020s vs target 2010s (1 decade apart, +0.21)
  2. Rooftop Lights — Indigo Parade (indie pop/happy)  score 4.62 = 57% of max
       - mood match: happy (+1.0)
       - energy 0.76 vs target 0.50 closeness 0.74 -> +1.48 pts
       - tempo 124 vs target 110 -> closeness 0.82 (+0.82)
       - danceability closeness 0.68 (+0.34)
       - acousticness closeness 0.85 (+0.42)
       - popularity 62 meets floor 50 (+0.3)
       - era 2010s vs target 2010s (same era, +0.25)
```

#### The one to read closely: `edge_gym_sad`

Block 4 is the key evidence in the whole card. The listener asked for mood `sad` and got
*Gym Hero* (intense), *Sunrise City* (happy) and *Thunder on Fifth Street* (confident) in the
top three — and the reason list for *Gym Hero* contains **no mood line at all**, because the
mood did not match. The mismatch is not hidden; it is simply worth less than the loudness
terms. Compare it against block 1, where *Sunrise City* earns a `mood match: happy (+1.0)` line
in the same position.

### Face validity: does `chill_lofi` feel right?

I picked the one profile I have strong opinions about — study lofi — and read the top 5 against
what I would actually play. Three of the five are right (*Library Rain*, *Midnight Coding*,
*Coffee Shop Stories*). Two are not, and both failures are instructive.

**Position 4 is the one that made me stop.** *Focus Flow* (lofi, `focused`) has a raw score of
6.55 — higher than *Spacewalk Thoughts* at 5.49 — yet it is ranked *below* it. That is the
diversity penalty working: *Focus Flow* is the third `lofi` song and the second *LoRoom* track
in the list, so it takes both penalties and loses 1.10 points. Musically I agree with the
result and disagree with the reason. The model demoted *Focus Flow* for being too similar to
songs already shown, which is exactly right, but it only got there by accident — it would have
ranked 3rd on merit, above a genuinely calmer track.

**Position 3 is the real disagreement.** *Spacewalk Thoughts* is ambient, not lofi. I asked for
lofi. The model correctly refused to give it the genre bonus (it loses 2.00 points there), and
then awarded it the slot anyway, because it wins on the two things I care about most in a study
playlist: it is quieter (energy closeness 0.94 vs 0.82) and it is actually `chill` (a mood match
worth 1.00). *Focus Flow* by contrast is labelled `focused`, not `chill`, so it forfeits the
mood point entirely — a distinction that is invisible to me, since both tracks are fine study
music.

**What this tells me.** The single-mood-label rule is the problem, not the weights. Half the
reason *Focus Flow* lost is that its mood word is `focused` and my profile's is `chill`, even
though I would happily put both in the same playlist. The catalog forces a song to pick one, and
the profile forces the listener to pick one, so two compatible things look incompatible to the
arithmetic. This is limitation 3 in the data section showing up as a wrong ranking, and it is
the strongest argument for the mood-distribution idea in "What I would build next".

### Profile-by-profile comparisons

Shared = songs common to both profiles' top 5 (out of 5).

| Pair of profiles | Shared | What changed, and why it makes sense |
|---|---:|---|
| `pop_happy` vs `chill_lofi` | 0/5 | Total disagreement, exactly as intended: bright, danceable pop versus quiet, heavily acoustic lofi. Zero overlap is the strongest evidence that the rule is actually listening to the profile. |
| `pop_happy` vs `intense_rock` | 1/5 | They share only *Gym Hero* — loud, fast and danceable. When two very different listeners both ask for high energy, the energy term drags the same song into both lists. |
| `pop_happy` vs `edge_gym_sad` | 2/5 | The edge profile kept pop, 2020s, danceability and popularity but flipped the mood to `sad`, and only **one** thing changed at the top. Mood is worth 1.00 against 2.00 for genre and up to 3.50 for the energy cluster, so a flipped mood barely moves a ranking that already agrees on loudness. |
| `pop_happy` vs `edge_acoustic_edm` | 2/5 | Both want energy 0.8–0.95 and high danceability, so they share *Gym Hero* and *Velvet Horizon*. The acousticness targets differ by 0.8 and it changes almost nothing, because that feature is only worth 0.50. |
| `pop_happy` vs `edge_off_catalog` | 0/5 | When genre and mood hit nothing, all scores compress into a 1.87-point band and the ordering is decided by whichever side features line up. It is a *different* arbitrary list, not a better one. |
| `pop_happy` vs `edge_all_mid` | 4/5 | Even with energy dragged to 0.50, the pop/happy categorical match (3.00) still beats every numeric mismatch. The categorical weights, not the numeric ones, decide the top for mainstream profiles. |
| `chill_lofi` vs `intense_rock` | 0/5 | Perfect opposites — the quietest and loudest profiles share nothing. |
| `chill_lofi` vs `edge_gym_sad` | 0/5 | Energy 0.22 versus 0.92 is the widest possible gap, so no song can satisfy both. Shows the energy term doing real work between extremes. |
| `chill_lofi` vs `edge_acoustic_edm` | 1/5 | Counter-intuitive but correct: even though `chill_lofi` wants acousticness 0.85 and the edge profile wants 0.90, the edge profile's genre and energy requests are so loud that they pull the list away from almost every calm song — only *Library Rain* survives in both. |
| `chill_lofi` vs `edge_off_catalog` | 1/5 | They meet only on *Midnight Coding* (lofi, energy 0.42). With no genre or mood anchors, the ranking collapses onto the energy axis. |
| `chill_lofi` vs `edge_all_mid` | 0/5 | A 0.50 energy target is still far from 0.22, so the mid-profile gets mid-energy songs while lofi stays low. Mid targets are nobody's favourite. |
| `intense_rock` vs `edge_gym_sad` | 3/5 | Nearly identical output from two profiles that disagree completely about mood. Both ask for loud, fast, aggressive-feeling music, and that is all the maths hears — the `sad` request is invisible. The single most alarming pair in the study. |
| `intense_rock` vs `edge_acoustic_edm` | 2/5 | Both are "loud" requests dressed in different labels (*rock* vs *edm*, acousticness 0.08 vs 0.90) and they still share two songs, because energy + tempo + danceability are worth 3.50 against genre's 2.00. Texture and label lose to loudness. |
| `intense_rock` vs `edge_off_catalog` | 0/5 | No shared anchors at all: one has a genre match and high energy, the other has neither. |
| `intense_rock` vs `edge_all_mid` | 1/5 | Only *Gym Hero* survives — the one track that scores on popularity, recency and danceability while being loud enough for the rock profile. |
| `edge_gym_sad` vs `edge_acoustic_edm` | 1/5 | Two contradictory profiles with almost the same answer: both asked for "high energy, loud, danceable" and got it. The conflicts are real to the user and invisible to the model. |
| `edge_gym_sad` vs `edge_off_catalog` | 0/5 | One is a loud request, the other a muted average; the energy axis alone separates them. |
| `edge_gym_sad` vs `edge_all_mid` | 2/5 | They keep only the categorical anchors (*Sunrise City*, *Gym Hero*). Every loud song the sad profile wants is knocked out of the mid profile's list by the energy target. |
| `edge_acoustic_edm` vs `edge_off_catalog` | 0/5 | The off-catalog profile has no genre bonus to give, so the acoustic profile's pop pick cannot appear — an artefact of one profile having a genre that exists. |
| `edge_acoustic_edm` vs `edge_all_mid` | 2/5 | *Gym Hero* and *Velvet Horizon* again: the shared loud/2020s/popular intersection. |
| `edge_off_catalog` vs `edge_all_mid` | 1/5 | Both end up dominated by era, popularity and tempo, so their "mediocre middle" lists resemble each other (*Slow Collapse*). |

### What surprised me

1. **The strongest pair of opposites produced almost *identical* lists.** `intense_rock` and
   `edge_gym_sad` share 3 of 5 songs (*Gym Hero*, *Storm Runner*, *Paper Cut Skyline*) despite
   disagreeing about the entire emotional point of the music — one wants `intense`, the other
   wants `sad`. I expected a wrong answer; I did not expect the wrongness to be that extreme.
2. **Being "too high" never hurts enough.** My intuition said a sad, intense listener was
   contradictory and would get a muddled list. Instead the model resolved the conflict silently
   and consistently in favour of loudness — it never surfaced the contradiction.
3. **The dataset was not the main problem.** The textbook bias ("60% of the catalog is pop") is
   absent here: only 6.5% of songs are pop, and 29 artists across 31 songs is close to unique.
   The bias came from the *weights*, which is more interesting and much harder to see.
4. **Most of the catalog is loud.** 19 of 31 songs have energy ≥ 0.70, so a mid-energy listener
   is structurally punished by a linear distance rule.
5. **The diversity penalty barely did anything.** An added fairness mechanism can be present,
   tested and almost inert — a good reminder to measure a safety feature rather than assume
   shipping it helped.
6. **The explanations were the most useful part.** In block 4, the line
   "mood tag overlap [none] 0.00 (+0.00)" sits directly above "energy 0.93 vs target 0.92
   closeness 0.99 -> +1.98 pts" — the same block awards zero for the emotional request and
   nearly two points for the loudness one, and there is no mood line at all between them. That
   juxtaposition is what made the bias obvious. The reasons exist for the user, but they turned
   out to be the best debugging tool I had.
7. **The printed reasons hide the misses.** `main.py` skips any line containing `(+0.0)`, so
   "mood mismatch: intense vs sad" never reaches the terminal — the *absence* of a mood line is
   the only signal, and absence is much easier to miss than a zero. The explicit mismatch text
   is available from `score_song(..., include_misses=True)`, which is how I confirmed it. A
   transparency feature that filters out bad news is only half transparent.

### Sensitivity experiments (Phase 4, Step 3)

Both applied to `pop_happy` on top of `balanced`.

**Experiment A — `--experiment weight_shift`:** double energy (2.00 → 4.00), halve genre
(2.00 → 1.00). Ceiling rises 8.05 → 9.05.

| Song | energy | balanced | weight_shift | change |
|---|---:|---:|---:|---:|
| Sunrise City | 0.82 | 7.94 | 8.90 | +0.96 |
| Gym Hero | 0.93 | 6.33 | 7.07 | +0.74 |
| Rooftop Lights | 0.76 | 5.74 | 7.66 | +1.92 |
| Velvet Horizon | 0.78 | 5.69 | 7.65 | +1.96 |
| Salsa del Sol | 0.82 | 4.64 | 6.61 | +1.96 |

Result: the top song was unchanged and positions 2–5 reshuffled — *Rooftop Lights* jumped from
3rd to 2nd and *Velvet Horizon* from 4th to 3rd, pushing *Gym Hero* down to 4th. With energy
worth 4.00, being *exactly* on target pays, and 0.76–0.82 is closer to 0.80 than 0.93 is. The
experiment did what the maths predicted (good sign for correctness), but the output became
**different, not more accurate**: *Sunrise City* still sits on top because halving a genre bonus
does not dislodge a song that is also winning on energy, tempo, tags, era and popularity. Genre
turned out to be **redundant** with the other features for mainstream pop.

**Experiment B — `--experiment no_mood`:** mood and mood tags off (1.00 → 0.00, 0.50 → 0.00).
Ceiling falls 8.05 → 6.55.

| Song | balanced | no_mood | change |
|---|---:|---:|---:|
| Sunrise City | 7.94 | 6.44 | −1.50 |
| Gym Hero | 6.33 | 6.08 | −0.25 |
| Rooftop Lights | 5.74 | 4.24 | −1.50 |
| Velvet Horizon | 5.69 | 4.44 | −1.25 |
| Salsa del Sol | 4.64 | 4.14 | −0.50 |
| Neon Cathedral | 4.62 | 4.37 | −0.25 |
| Hyperfocus | 4.17 | 4.17 | 0.00 |

Result: the top of the list was unchanged, but positions 3–5 churned — *Rooftop Lights* and
*Velvet Horizon* fell, *Neon Cathedral* and *Hyperfocus* rose. The mood term was the *only*
thing lifting happy and pop-adjacent tracks above the loud, generic ones, so removing it helped
exactly the songs that had been collecting points without an emotional match.

**Combined verdict:** the model is *stable* at the top (the same two songs win under three
different weightings) and *fragile* in the middle (positions 3–5 reshuffle whenever a weight
moves). A recommender whose top 2 never change, no matter how you retune it, has found a shortcut
rather than a taste.

### Diversity penalty: measured effect

| Profile | Song penalised | Amount | Position before → after | Top 5 changed? |
|---|---|---:|---|---|
| `pop_happy` | Gym Hero | −0.35 | 2 → 2 | no |
| `edge_gym_sad` | Sunrise City | −0.35 | 2 → 2 | no |
| `edge_all_mid` | Gym Hero | −0.35 | 2 → 3 | **yes** — *Rooftop Lights* overtakes it |
| `edge_off_catalog` | Focus Flow | −0.35 | 3 → 21 (of 31) | **yes** — *Quiet Machines* moves up |
| `edge_acoustic_edm` | Sunrise City | −0.35 | 4 → 4 | no |
| `chill_lofi` | Focus Flow | −0.35 | 3 → 4 | **yes** — *Spacewalk Thoughts* overtakes it |
| `intense_rock` | Sunrise City | −0.35 | 8 → 8 | no |

The mechanism works as designed — it refuses to place two genre-identical songs back-to-back —
but on a 31-song catalog where only five genres hold more than one song it rarely fires, and it
never touched the number-one recommendation. Documented as a **measured but nearly inert**
fairness feature rather than claimed as a success.

---

## Intended Use and Non-Intended Use

**Intended use**

- A teaching artefact: demonstrating how input features, a scoring rule and a ranking rule
  combine into a recommendation.
- A sandbox for experimenting with weights, modes and fairness rules, with fully explainable
  output.
- A portfolio example of "explainable by default" design — every score is traceable.
- Proof that a recommender does not need machine learning to exhibit recognisable human-like
  behaviour (and recognisable biases).

**Not intended use**

- ❌ **Any real product or playlist generation for real users.** 31 songs is not a catalog.
- ❌ **Inferring anything about a real person's taste** or using it to profile anyone. The
  "profiles" are invented dictionaries, not people.
- ❌ **Deciding what music gets promoted.** The popularity floor and the genre weight would
  systematically bury small artists.
- ❌ **Any emotional or mental-health context.** The `sad` mood is a string label, and the system
  provably ignores it when energy is high — do not use it to choose "calming" music for someone
  who needs it.
- ❌ **As evidence of how Spotify or TikTok work.** This is content-based-only, with no
  collaborative filtering, no neural models and no behavioural data.

## Ideas for Improvement

1. **Score `valence` too, and make mood a two-dimensional target** (valence × energy) instead of
   a single word. This directly fixes the "sad but high energy" failure: sadness lives in low
   valence, not low energy, so the two requests would stop cancelling each other.
2. **Make the weights learned, not hand-set.** Log skips and completions, then fit the weights
   so the model stops encoding my own idea of what matters. This is the step that turns it into a
   hybrid recommender.
3. **Replace the hard popularity floor with a fairness constraint** — reserve one of the five
   slots for a song below the popularity threshold (a "long tail" quota).
4. **Add uncertainty reporting.** If the best score is under ~50% of the ceiling (the cold-start
   case), print "low confidence — I do not have a good match" instead of a ranked list that looks
   authoritative.
5. **Make the diversity penalty scale-aware** — penalise by how *much* of the list a genre has
   already taken, and enforce a hard cap (max 2 songs per genre), then re-measure that it
   changes something.
6. **Grow the catalog and add a second, independent label source** so the labels are not just my
   opinion, and gender/language/era balance can be audited.
7. **Add list-level explanations** — "4 of your 5 picks were pop because your profile weights
   genre heavily." The *user* should be able to see the same filter bubble the engineer sees.

---

## Personal Reflection

**What was your biggest learning moment during this project?**

The moment I read the full 31-song ranking for the "sad but high energy" profile and saw
*Paper Lungs* sitting at number 13. I had built the scoring rule myself, I had written
the mood check myself, and I still did not predict that a single flipped word would be
overruled by three numeric features. It taught me that a weight is not a preference — it is a
policy, and it silently decides whose request wins when a user's requests conflict. That is the
difference between "the code does what I wrote" and "the code does what the user meant."

**How did using AI tools help you, and when did you need to double-check them?**

AI help was genuinely useful in three specific ways: explaining collaborative versus
content-based filtering in concrete terms, suggesting the *closeness* formula
($1 - |song - target|$) instead of "higher is better," and reviewing the ranking loop so that
`sorted()` was used without mutating the catalog. It also suggested the four-mode weight-table
design, which removed a whole class of branching bugs.

I had to double-check it constantly, and the checks mattered:

- The first version of `load_songs()` returned `release_decade` as the *string* `"2020s"`,
  which silently became `0` when cast — so every era comparison failed quietly instead of
  raising an error. The maths still "worked"; the answer was just wrong.
- A suggested scoring rule rewarded *higher* energy rather than *closer* energy. It looked
  plausible in the diff, and only a test (does 0.99 score better than 0.80 for a 0.80 target?)
  caught it.
- Two of the advanced features I asked for were added to the CSV but never actually scored, so
  the model and the description disagreed. I caught that by writing an assertion that the
  weights table and the code agreed on which features exist.

The lesson: AI is fast at *plausible*, and plausible is not the same as *verified*. Every number
in this model card came from running the code and reading the output, not from trusting a
description of the code.

**What surprised you about how simple algorithms can still "feel" like recommendations?**

I expected 20 lines of addition to look like arithmetic. Instead the lofi list (quiet, acoustic,
calm) and the pop list (bright, danceable, 2020s) had **zero songs in common**, and both lists
read as if a person had chosen them. What convinced me was reading the *reasons* out loud, not
the scores: "genre match: pop (+2.0), mood match: happy (+1.0), energy 0.82 vs target 0.80
closeness 0.98" is a sentence a human would say. The magic is not in the model — it is in the
fact that a handful of well-chosen attributes already describe a "vibe" well enough. The flip side arrived immediately: the same
simple maths produced a filter bubble just as convincingly, and the *Gym Hero* result was
reported with total confidence. Simple does not mean safe; it means the bias is legible if you
bother to look.

**What would you try next if you extended this project?**

I would replace the single `mood` word with a two-dimensional (valence, energy) target, because
that single change fixes the biggest failure I found without adding any new data. After that I
would add a proper listening simulation — an agent that "skips" a recommendation it should not
like — and tune the weights against those simulated skips, so the weights stop being my opinion
and start being evidence. Finally I would build the diversity mechanism properly: a hard cap per
genre with a long-tail quota, plus a test that asserts it actually changes the output. A fairness
feature that never fires is not a fairness feature.