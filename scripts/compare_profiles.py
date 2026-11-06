"""Side-by-side comparison of every profile and both sensitivity experiments.

Run:  python -m scripts.compare_profiles
"""

import sys
sys.path.insert(0, ".")
from src.main import EXPERIMENTS  # noqa: E402
from src.recommender import (  # noqa: E402
    SCORING_MODES,
    load_profiles,
    load_songs,
    max_score,
    recommend_songs,
)

def top_names(prefs, songs, k=5, mode="balanced", diversify=True):
    """Return just the song titles of a ranking, for compact side-by-side output.

    A thin wrapper over recommend_songs() so sections B and C can print one
    line per configuration instead of a full table.
    """
    return [r["song"]["title"] for r in recommend_songs(
        prefs, songs, k=k, mode=mode, diversify=diversify)]

def main():
    """Run the three comparison studies and print them to stdout.

    A. every profile's top 5 in balanced mode, with raw and final scores
    B. pairwise overlap between profiles, testing whether the rule separates
       genuinely different tastes or collapses onto the same loud songs
    C. the two sensitivity experiments plus the diversity penalty on/off,
       showing how stable each ranking is under a changed weighting

    Reads data/songs.csv and data/profiles.json, so it reports on whatever the
    current catalog holds rather than on hardcoded expectations.
    """
    songs = load_songs()
    profiles = load_profiles()
    print(f"Catalog: {len(songs)} songs\n")

    print("=== A. Every profile, balanced mode, top 5 ===")
    baseline = {}
    for name, prefs in profiles.items():
        results = recommend_songs(prefs, songs, k=5)
        baseline[name] = [r["song"]["title"] for r in results]
        print(f"\n{name}  ({prefs['label']})")
        for rank, r in enumerate(results, 1):
            s = r["song"]
            print(f"  {rank}. {s['title']:22s} {s['genre']:10s} {s['mood']:12s} "
                  f"score={r['score']:.2f} final={r['final_score']:.2f}")

    print("\n\n=== B. Do different profiles actually get different songs? ===")
    names = list(profiles)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = len(set(baseline[a]) & set(baseline[b]))
            print(f"  {a:18s} vs {b:18s} -> {overlap}/5 shared: "
                  f"{sorted(set(baseline[a]) & set(baseline[b]))}")

    print("\n\n=== C. Sensitivity experiments on pop_happy (balanced) ===")
    prefs = profiles["pop_happy"]
    print(f"  baseline    : {top_names(prefs, songs)}")
    for exp_name, override in EXPERIMENTS.items():
        mode = dict(SCORING_MODES["balanced"])
        mode.update(override)
        print(f"  {exp_name:12s}: {top_names(prefs, songs, mode=mode)}")
        print(f"  {'':12s}  (max possible score now {max_score(mode):.2f})")

    print("\n  Diversity penalty OFF vs ON for chill_lofi:")
    prefs = profiles["chill_lofi"]
    print(f"    OFF: {top_names(prefs, songs, diversify=False)}")
    print(f"    ON : {top_names(prefs, songs, diversify=True)}")

if __name__ == "__main__":
    main()