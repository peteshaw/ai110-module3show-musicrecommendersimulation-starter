"""Command-line entry point for VibeFinder 1.0.

Run with:  python -m src.main
           python -m src.main --profile chill_lofi --k 5
           python -m src.main --profile all --mode energy_focused
"""

import argparse

# Work both as `python -m src.main` (package) and `python src/main.py` (script).
try:
    from .recommender import (
        SCORING_MODES,
        format_recommendations,
        load_songs,
        max_score,
        mode_label,
        recommend_songs,
    )
except ImportError:  # pragma: no cover
    from recommender import (  # type: ignore
        SCORING_MODES,
        format_recommendations,
        load_songs,
        max_score,
        mode_label,
        recommend_songs,
    )

# ---------------------------------------------------------------------------
# Taste profiles. "label" is display-only; everything else is read by
# score_song(). Realistic profiles first, adversarial "trick" profiles after.
# ---------------------------------------------------------------------------
PROFILES = {
    "pop_happy": {
        "label": "Happy Pop (default)",
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.80,
        "target_tempo_bpm": 120,
        "target_danceability": 0.80,
        "target_acousticness": 0.10,
        "mood_tags": ["euphoric", "playful"],
        "min_popularity": 60,
        "target_decade": 2020,
    },
    "chill_lofi": {
        "label": "Chill Lofi / Study",
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.22,
        "target_tempo_bpm": 85,
        "target_danceability": 0.60,
        "target_acousticness": 0.85,
        "mood_tags": ["calm", "focused"],
        "min_popularity": 40,
        "target_decade": 2010,
    },
    "intense_rock": {
        "label": "Deep Intense Rock",
        "favorite_genre": "rock",
        "favorite_mood": "intense",
        "target_energy": 0.90,
        "target_tempo_bpm": 140,
        "target_danceability": 0.55,
        "target_acousticness": 0.08,
        "mood_tags": ["aggressive", "gritty"],
        "min_popularity": 50,
        "target_decade": 2000,
    },
    "edge_gym_sad": {
        "label": "EDGE: high energy but sad mood (conflicting)",
        "favorite_genre": "pop",
        "favorite_mood": "sad",
        "target_energy": 0.92,
        "target_tempo_bpm": 128,
        "target_danceability": 0.90,
        "target_acousticness": 0.05,
        "mood_tags": ["aggressive"],
        "min_popularity": 80,
        "target_decade": 2020,
    },
    "edge_acoustic_edm": {
        "label": "EDGE: EDM genre but acoustic/mellow (conflicting)",
        "favorite_genre": "edm",
        "favorite_mood": "chill",
        "target_energy": 0.95,
        "target_tempo_bpm": 128,
        "target_danceability": 0.90,
        "target_acousticness": 0.90,
        "mood_tags": ["peaceful"],
        "min_popularity": 30,
        "target_decade": 2020,
    },
    "edge_off_catalog": {
        "label": "EDGE: genre/mood that do not exist in the catalog (cold start)",
        "favorite_genre": "vaporwave",
        "favorite_mood": "dreamy",
        "target_energy": 0.50,
        "target_tempo_bpm": 100,
        "target_danceability": 0.50,
        "target_acousticness": 0.50,
        "mood_tags": ["night-drive"],
        "min_popularity": 99,
        "target_decade": 1980,
    },
    "edge_all_mid": {
        "label": "EDGE: every target dead-center (does the energy weight break ties?)",
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.50,
        "target_tempo_bpm": 110,
        "target_danceability": 0.50,
        "target_acousticness": 0.50,
        "mood_tags": [],
        "min_popularity": 50,
        "target_decade": 2010,
    },
}

DEFAULT_PROFILE = "pop_happy"

def print_results(profile_name, prefs, songs, mode, k, diversify):
    """Score, rank and pretty-print one profile's top k recommendations."""
    results = recommend_songs(prefs, songs, k=k, mode=mode, diversify=diversify)
    ceiling = max_score(mode)

    print("=" * 78)
    print(f"PROFILE: {prefs.get('label', profile_name)}   [{profile_name}]")
    print(f"MODE: {mode_label(mode)}  |  top {k} of {len(songs)} songs  |  "
          f"diversity penalty: {'ON' if diversify else 'OFF'}  |  "
          f"max possible raw score: {ceiling:.2f}")
    print("=" * 78)
    print(format_recommendations(results, mode=mode))
    print()
    print("Why each song was chosen:")
    for rank, item in enumerate(results, start=1):
        song = item["song"]
        pct = 100 * item["final_score"] / ceiling
        note = f"  (diversity -{item['penalty']:.2f})" if item["penalty"] else ""
        print(f"  {rank}. {song['title']} — {song['artist']} "
              f"({song['genre']}/{song['mood']})  score {item['score']:.2f} "
              f"= {pct:.0f}% of max{note}")
        for reason in item["reasons"]:
            if "(+0.0)" in reason:
                continue  # hide the misses to keep the summary short
            print(f"       - {reason}")
    print()

# ---------------------------------------------------------------------------
# Sensitivity experiments (Phase 4, Step 3). Each one returns a partial dict
# of weight overrides that _mode_weights() merges over the 'balanced' recipe.
# ---------------------------------------------------------------------------
EXPERIMENTS = {
    # Energy counts double; genre counts half. Tests how much the categorical
    # head-start is really driving the ranking.
    "weight_shift": {"energy": 4.0, "genre": 1.0},
    # Mood is switched off entirely. Tests whether dropping a whole feature
    # changes the order of results or only shuffles the middle of the list.
    "no_mood": {"mood": 0.0, "mood_tags": 0.0},
}

def resolve_mode(mode_name, experiment):
    """Return (mode_object, printable_label) after applying an experiment."""
    if not experiment:
        return mode_name, mode_name
    override = EXPERIMENTS[experiment]
    return override, f"{mode_name} + {experiment} {override}"

def build_parser():
    """Define the CLI surface."""
    parser = argparse.ArgumentParser(description="VibeFinder 1.0 - content-based music recommender")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help=f"profile name, or 'all'. Options: {', '.join(PROFILES)}")
    parser.add_argument("--mode", default="balanced", choices=sorted(SCORING_MODES),
                        help="scoring/ranking strategy")
    parser.add_argument("--k", type=int, default=5, help="how many recommendations to show")
    parser.add_argument("--no-diversity", action="store_true",
                        help="disable the diversity penalty (raw scores only)")
    parser.add_argument("--experiment", choices=sorted(EXPERIMENTS), default=None,
                        help="apply a sensitivity experiment on top of --mode")
    parser.add_argument("--list-profiles", action="store_true", help="print available profiles and exit")
    return parser

def main(argv=None):
    """Load the catalog and print recommendations for one or all profiles."""
    args = build_parser().parse_args(argv)

    if args.list_profiles:
        for name, prefs in PROFILES.items():
            print(f"{name:20s} {prefs.get('label', '')}")
        return 0

    songs = load_songs()
    print(f"Loaded songs: {len(songs)}")
    print(f"Catalog spans {len({s['genre'] for s in songs})} genres and "
          f"{len({s['mood'] for s in songs})} moods.\n")

    if args.profile == "all":
        names = list(PROFILES)
    elif args.profile in PROFILES:
        names = [args.profile]
    else:
        raise SystemExit(f"Unknown profile {args.profile!r}. Try --list-profiles")

    mode_obj, _ = resolve_mode(args.mode, args.experiment)
    for name in names:
        print_results(name, PROFILES[name], songs, mode_obj, args.k, not args.no_diversity)

    print("Done. Re-run with --mode energy_focused or --no-diversity to compare strategies.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())