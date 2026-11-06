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
        load_profiles,
        load_songs,
        max_score,
        mode_label,
        recommend_songs,
    )
except ImportError:  # pragma: no cover
    from recommender import (  # type: ignore
        SCORING_MODES,
        format_recommendations,
        load_profiles,
        load_songs,
        max_score,
        mode_label,
        recommend_songs,
    )

# Taste profiles live in data/profiles.json (loaded by load_profiles()) so a
# new listener can be added by editing data, not code. "label" is display-only;
# everything else is read by score_song(). Realistic profiles first,
# adversarial "trick" profiles after.
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

def build_parser(profiles):
    """Define the CLI surface and return the configured argparse parser.

    ``profiles`` supplies the valid --profile names, so the help text and the
    error message stay in sync with data/profiles.json without hardcoding them.
    """
    parser = argparse.ArgumentParser(description="VibeFinder 1.0 - content-based music recommender")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help=f"profile name, or 'all'. Options: {', '.join(profiles)}")
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
    profiles = load_profiles()
    args = build_parser(profiles).parse_args(argv)

    if args.list_profiles:
        for name, prefs in profiles.items():
            print(f"{name:20s} {prefs.get('label', '')}")
        return 0

    songs = load_songs()
    print(f"Loaded songs: {len(songs)}")
    print(f"Catalog spans {len({s['genre'] for s in songs})} genres and "
          f"{len({s['mood'] for s in songs})} moods.\n")

    if args.profile == "all":
        names = list(profiles)
    elif args.profile in profiles:
        names = [args.profile]
    else:
        raise SystemExit(f"Unknown profile {args.profile!r}. Try --list-profiles")

    mode_obj, _ = resolve_mode(args.mode, args.experiment)
    for name in names:
        print_results(name, profiles[name], songs, mode_obj, args.k, not args.no_diversity)

    print("Done. Re-run with --mode energy_focused or --no-diversity to compare strategies.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())