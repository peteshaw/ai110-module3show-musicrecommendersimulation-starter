"""Core scoring and ranking logic for VibeFinder 1.0.

Pipeline:  data/songs.csv -> load_songs() -> score_song() (one song)
           -> recommend_songs() (whole list, ranked) -> terminal table.
"""

import csv
import os

# Path to the catalog, resolved relative to this file so it works from anywhere.
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "songs.csv")

# --- Feature typing ---------------------------------------------------------
# Every column the maths touches must leave the CSV as a number, not a string.
NUMERIC_FIELDS = (
    "energy",
    "tempo_bpm",
    "valence",
    "danceability",
    "acousticness",
    "popularity",
    "release_decade",
)
FLOAT_FIELDS = ("energy", "valence", "danceability", "acousticness")
INT_FIELDS = ("tempo_bpm", "popularity", "release_decade", "id")
NUMERIC_SET = set(FLOAT_FIELDS) | set(INT_FIELDS)

# Largest tempo gap we are willing to measure before closeness hits zero.
MAX_TEMPO_GAP = 80.0

# --- Algorithm recipe -------------------------------------------------------
# Each mode is a plain dict of weights. The 'balanced' mode is the default
# recipe documented in README.md.
SCORING_MODES = {
    "balanced": {
        "genre": 2.0,
        "mood": 1.0,
        "energy": 2.0,
        "tempo": 1.0,
        "danceability": 0.5,
        "acousticness": 0.5,
        "mood_tags": 0.5,
        "popularity": 0.3,
        "decade": 0.25,
    },
    "genre_first": {
        "genre": 4.0,
        "mood": 0.5,
        "energy": 1.0,
        "tempo": 0.5,
        "danceability": 0.25,
        "acousticness": 0.25,
        "mood_tags": 0.25,
        "popularity": 0.2,
        "decade": 0.25,
    },
    "mood_first": {
        "genre": 1.0,
        "mood": 3.0,
        "energy": 1.5,
        "tempo": 0.75,
        "danceability": 0.5,
        "acousticness": 0.5,
        "mood_tags": 1.0,
        "popularity": 0.25,
        "decade": 0.25,
    },
    "energy_focused": {
        "genre": 0.5,
        "mood": 0.5,
        "energy": 4.0,
        "tempo": 1.0,
        "danceability": 1.0,
        "acousticness": 0.25,
        "mood_tags": 0.25,
        "popularity": 0.2,
        "decade": 0.25,
    },
}

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_songs(path=DATA_PATH):
    """Read the CSV catalog and return a list of dicts with numeric fields cast."""
    songs = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            song = {}
            for key, value in row.items():
                if key is None:  # ragged row / trailing junk
                    continue
                key = key.strip()
                value = (value or "").strip()
                if key == "mood_tags":
                    # Stored as "euphoric|playful|bright" -> list[str].
                    song[key] = [t for t in value.split("|") if t]
                elif key in NUMERIC_SET:
                    song[key] = _to_number(key, value)
                else:
                    song[key] = value
            songs.append(song)
    return songs

def _to_number(key, value):
    """Cast one CSV cell to int or float, falling back to 0 on bad data.

    Handles the decade labels used in the CSV ("2020s" -> 2020) so we can
    measure how many decades apart a song is from a listener's preference.
    """
    text = str(value).strip().rstrip("s")
    try:
        return int(float(text)) if key in INT_FIELDS else float(text)
    except (TypeError, ValueError):
        return 0

# ---------------------------------------------------------------------------
# Scoring one song  (the "judge")
# ---------------------------------------------------------------------------
def _closeness(song_value, target_value):
    """Return 0.0-1.0 for how close a 0-1 feature is to the target.

    A song sitting exactly on the target scores 1.0; a song at the opposite
    end of the scale scores 0.0. This is a linear decay on the gap, so being
    'too much' is penalised exactly as hard as being 'too little'.
    """
    try:
        gap = abs(float(song_value) - float(target_value))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, 1.0 - gap)

def _tempo_closeness(song_bpm, target_bpm, max_gap=MAX_TEMPO_GAP):
    """Closeness for tempo, which lives on a BPM scale instead of 0-1."""
    try:
        gap = abs(float(song_bpm) - float(target_bpm))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, 1.0 - gap / max_gap)

def _tag_overlap(song_tags, target_tags):
    """Fraction of the user's desired mood tags that the song actually has."""
    if not target_tags:
        return 0.0
    wanted = {t.strip().lower() for t in target_tags}
    have = {t.strip().lower() for t in (song_tags or [])}
    return len(wanted & have) / len(wanted)

def score_song(user_prefs, song, mode="balanced", include_misses=True):
    """Score one song against one taste profile.

    Returns (score, reasons): a float and a list of human-readable strings that
    explain exactly where every point came from.
    """
    if isinstance(mode, dict):
        weights = _mode_weights(mode)
    elif mode in SCORING_MODES:
        weights = SCORING_MODES[mode]
    else:
        raise ValueError(f"Unknown mode {mode!r}. Choose from {sorted(SCORING_MODES)}")
    score = 0.0
    reasons = []

    # --- Categorical checks: all-or-nothing ---
    fav_genre = (user_prefs.get("favorite_genre") or "").strip().lower()
    if fav_genre:
        if (song.get("genre") or "").strip().lower() == fav_genre:
            score += weights["genre"]
            reasons.append(f"genre match: {song['genre']} (+{weights['genre']:.1f})")
        elif include_misses:
            reasons.append(f"genre mismatch: {song.get('genre', '?')} vs {fav_genre} (+0.0)")

    fav_mood = (user_prefs.get("favorite_mood") or "").strip().lower()
    if fav_mood:
        if (song.get("mood") or "").strip().lower() == fav_mood:
            score += weights["mood"]
            reasons.append(f"mood match: {song['mood']} (+{weights['mood']:.1f})")
        elif include_misses:
            reasons.append(f"mood mismatch: {song.get('mood', '?')} vs {fav_mood} (+0.0)")

    # --- Numerical similarity: partial credit, decays with the gap ---
    if "target_energy" in user_prefs:
        c = _closeness(song.get("energy"), user_prefs["target_energy"])
        score += c * weights["energy"]
        reasons.append(
            f"energy {song.get('energy'):.2f} vs target {user_prefs['target_energy']:.2f} "
            f"closeness {c:.2f} -> +{c * weights['energy']:.2f} pts"
        )

    if "target_tempo_bpm" in user_prefs:
        c = _tempo_closeness(song.get("tempo_bpm"), user_prefs["target_tempo_bpm"])
        score += c * weights["tempo"]
        reasons.append(
            f"tempo {song.get('tempo_bpm')} vs target {user_prefs['target_tempo_bpm']} "
            f"-> closeness {c:.2f} (+{c * weights['tempo']:.2f})"
        )

    if "target_danceability" in user_prefs:
        c = _closeness(song.get("danceability"), user_prefs["target_danceability"])
        score += c * weights["danceability"]
        reasons.append(f"danceability closeness {c:.2f} (+{c * weights['danceability']:.2f})")

    if "target_acousticness" in user_prefs:
        c = _closeness(song.get("acousticness"), user_prefs["target_acousticness"])
        score += c * weights["acousticness"]
        reasons.append(f"acousticness closeness {c:.2f} (+{c * weights['acousticness']:.2f})")

    # --- Advanced feature: detailed mood tags ---
    if user_prefs.get("mood_tags"):
        c = _tag_overlap(song.get("mood_tags"), user_prefs["mood_tags"])
        score += c * weights["mood_tags"]
        hit = sorted({
            t.strip().lower() for t in user_prefs["mood_tags"]
        } & {t.lower() for t in (song.get("mood_tags") or [])})
        label = ", ".join(hit) if hit else "none"
        reasons.append(f"mood tag overlap [{label}] {c:.2f} (+{c * weights['mood_tags']:.2f})")

    # --- Advanced feature: popularity (0-100, small tie-breaker nudge) ---
    if "min_popularity" in user_prefs:
        if song.get("popularity", 0) >= user_prefs["min_popularity"]:
            score += weights["popularity"]
            reasons.append(
                f"popularity {song.get('popularity')} meets floor "
                f"{user_prefs['min_popularity']} (+{weights['popularity']:.1f})"
            )
        elif include_misses:
            reasons.append(
                f"popularity {song.get('popularity')} under floor "
                f"{user_prefs['min_popularity']} (+0.0)"
            )

    # --- Advanced feature: release decade (era closeness) ---
    if "target_decade" in user_prefs:
        try:
            gap = abs(float(song.get("release_decade", 0)) - float(user_prefs["target_decade"])) / 10.0
            c = max(0.0, 1.0 - gap / 6.0)
        except (TypeError, ValueError):
            c = 0.0
        score += c * weights["decade"]
        if gap == 0:
            era_note = "same era"
        else:
            era_note = f"{gap:.0f} decade{'' if gap == 1 else 's'} apart"
        reasons.append(
            f"era {song.get('release_decade')}s vs target {user_prefs['target_decade']}s "
            f"({era_note}, +{c * weights['decade']:.2f})"
        )

    return round(score, 4), reasons

def _mode_weights(mode):
    """Return a full weights dict for a mode name or a partial override dict."""
    if isinstance(mode, dict):
        weights = dict(SCORING_MODES["balanced"])
        weights.update(mode)
        return weights
    if mode not in SCORING_MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from {sorted(SCORING_MODES)}")
    return SCORING_MODES[mode]

def mode_label(mode):
    """Human-readable name for a mode (name or custom weights dict)."""
    if isinstance(mode, dict):
        changed = ", ".join(f"{k} x{v:g}" for k, v in sorted(mode.items()))
        return f"balanced+experiment({changed})"
    return mode

def max_score(mode="balanced"):
    """Highest score any song could earn in a given mode (used for percentage display)."""
    return sum(_mode_weights(mode).values())

# ---------------------------------------------------------------------------
# Ranking a list  (the "recommender")
# ---------------------------------------------------------------------------
def _diversity_penalty(song, chosen, artist_penalty, genre_penalty):
    """Points removed from a candidate for repeating an artist/genre already shown."""
    penalty = 0.0
    if any(song.get("artist") == c["song"].get("artist") for c in chosen):
        penalty += artist_penalty
    if any(song.get("genre") == c["song"].get("genre") for c in chosen):
        penalty += genre_penalty
    return penalty

def recommend_songs(user_prefs, songs, k=5, mode="balanced",
                    diversify=True, artist_penalty=0.75, genre_penalty=0.35):
    """Rank the catalog for one profile and return the top k explained results.

    Step 1: every song is judged independently by score_song().
    Step 2: results are sorted highest-to-lowest.
    Step 3: (optional) a greedy re-selection pass applies a diversity penalty so
            the same artist/genre cannot dominate the top of the list.

    Returns a list of dicts: song, score, reasons, penalty, final_score.
    """
    judged = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, mode=mode)
        judged.append({
            "song": song,
            "score": score,
            "reasons": reasons,
            "penalty": 0.0,
            "final_score": score,
        })

    # sorted() returns a NEW list (unlike list.sort(), which mutates in place).
    ranked = sorted(judged, key=lambda item: item["score"], reverse=True)

    if not diversify:
        return ranked[:k]

    # Greedy re-selection: each round, pick the best candidate AFTER penalties.
    pool = list(ranked)
    chosen = []
    while pool and len(chosen) < k:
        best_index, best_value, best_penalty = 0, None, 0.0
        for index, item in enumerate(pool):
            penalty = _diversity_penalty(
                item["song"], chosen, artist_penalty, genre_penalty
            )
            value = item["score"] - penalty
            if best_value is None or value > best_value:
                best_index, best_value, best_penalty = index, value, penalty
        winner = pool.pop(best_index)
        winner["penalty"] = round(best_penalty, 2)
        winner["final_score"] = round(winner["score"] - best_penalty, 4)
        chosen.append(winner)
    return chosen

# ---------------------------------------------------------------------------
# Presentation helper
# ---------------------------------------------------------------------------
def format_recommendations(results, mode="balanced", use_tabulate=None, compact=True):
    """Render a ranked list as a readable table (tabulate if installed).

    With compact=True the long 'why' text is trimmed in the table and printed
    in full underneath, which keeps the terminal layout readable.
    """
    if use_tabulate is None:
        try:
            import tabulate  # noqa: F401
            use_tabulate = True
        except ImportError:
            use_tabulate = False

    rows = []
    for rank, item in enumerate(results, start=1):
        song = item["song"]
        detail = " | ".join(item["reasons"])
        rows.append([
            rank,
            song.get("title"),
            song.get("artist"),
            song.get("genre"),
            song.get("mood"),
            f"{item['score']:.2f}",
            f"-{item['penalty']:.2f}" if item["penalty"] else "-",
            detail,
        ])
    headers = ["#", "title", "artist", "genre", "mood", "score", "div.pen"]
    plain = [row[:7] for row in rows]

    if use_tabulate:
        from tabulate import tabulate
        return tabulate(plain, headers=headers, tablefmt="grid")
    return _ascii_table(headers, plain)

def _ascii_table(headers, rows, max_cell=None):
    """Minimal stdlib table renderer so the CLI works with zero dependencies."""
    def cell(value):
        text = str(value)
        if max_cell and len(text) > max_cell:
            return text[: max_cell - 3] + "..."
        return text

    body = [[cell(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in body:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))

    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [line, "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", line]
    for row in body:
        out.append("| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |")
    out.append(line)
    return "\n".join(out)