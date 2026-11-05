"""Tests for the VibeFinder 1.0 scoring and ranking logic.

Run with:  python -m unittest discover -s tests -v
(These also work under pytest if you have it installed.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.recommender import (  # noqa: E402
    SCORING_MODES,
    load_profiles,
    load_songs,
    max_score,
    recommend_songs,
    score_song,
)

PROFILE = {
    "favorite_genre": "pop",
    "favorite_mood": "happy",
    "target_energy": 0.80,
    "target_tempo_bpm": 120,
    "target_danceability": 0.80,
    "target_acousticness": 0.10,
    "mood_tags": ["euphoric"],
    "min_popularity": 60,
    "target_decade": 2020,
}

def make_song(**overrides):
    """Build a throwaway song dict for isolated tests."""
    song = {
        "id": 999, "title": "Test Track", "artist": "Nobody", "genre": "pop",
        "mood": "happy", "energy": 0.80, "tempo_bpm": 120, "valence": 0.7,
        "danceability": 0.8, "acousticness": 0.1, "popularity": 70,
        "release_decade": 2020, "mood_tags": ["euphoric"],
    }
    song.update(overrides)
    return song

class TestLoadSongs(unittest.TestCase):
    def test_loads_whole_catalog(self):
        songs = load_songs()
        self.assertGreaterEqual(len(songs), 10)

    def test_numeric_fields_are_numbers_not_strings(self):
        for song in load_songs():
            self.assertIsInstance(song["energy"], float, song["title"])
            self.assertIsInstance(song["tempo_bpm"], int, song["title"])
            self.assertIsInstance(song["popularity"], int, song["title"])
            self.assertIsInstance(song["release_decade"], int, song["title"])
            self.assertEqual(song["release_decade"] % 10, 0, "decade should be 1990/2000/...")

    def test_zero_to_one_features_stay_in_range(self):
        for song in load_songs():
            for field in ("energy", "valence", "danceability", "acousticness"):
                self.assertGreaterEqual(song[field], 0.0)
                self.assertLessEqual(song[field], 1.0)

    def test_mood_tags_parsed_into_a_list(self):
        song = load_songs()[0]
        self.assertIsInstance(song["mood_tags"], list)
        self.assertTrue(all(isinstance(t, str) and t for t in song["mood_tags"]))

    def test_no_duplicate_titles(self):
        titles = [s["title"] for s in load_songs()]
        self.assertEqual(len(titles), len(set(titles)))

class TestLoadProfiles(unittest.TestCase):
    """data/profiles.json is hand-edited data, so it needs the same checks as the CSV."""

    def test_loads_every_profile(self):
        profiles = load_profiles()
        self.assertGreaterEqual(len(profiles), 5)
        self.assertIn("pop_happy", profiles)

    def test_numeric_targets_are_numbers_not_strings(self):
        for name, prefs in load_profiles().items():
            for key in ("target_energy", "target_danceability", "target_acousticness"):
                self.assertIsInstance(prefs[key], float, f"{name}.{key}")
            for key in ("target_tempo_bpm", "min_popularity", "target_decade"):
                self.assertIsInstance(prefs[key], int, f"{name}.{key}")

    def test_unit_targets_stay_in_range(self):
        for name, prefs in load_profiles().items():
            for key in ("target_energy", "target_danceability", "target_acousticness"):
                self.assertGreaterEqual(prefs[key], 0.0, f"{name}.{key}")
                self.assertLessEqual(prefs[key], 1.0, f"{name}.{key}")

    def test_mood_tags_are_a_list_of_strings(self):
        for name, prefs in load_profiles().items():
            self.assertIsInstance(prefs["mood_tags"], list, name)
            self.assertTrue(all(isinstance(t, str) for t in prefs["mood_tags"]), name)

    def test_every_profile_scores_without_error(self):
        songs = load_songs()
        for name, prefs in load_profiles().items():
            score, reasons = score_song(prefs, songs[0])
            self.assertIsInstance(score, float, name)
            self.assertTrue(reasons, name)

    def test_malformed_json_raises(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
            path = f.name
        with self.assertRaises(ValueError):
            load_profiles(path)

    def test_out_of_range_target_raises(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"bad": {"target_energy": 1.5}}, f)
            path = f.name
        with self.assertRaises(ValueError):
            load_profiles(path)

class TestScoreSong(unittest.TestCase):
    def test_returns_score_and_reasons(self):
        score, reasons = score_song(PROFILE, make_song())
        self.assertIsInstance(score, float)
        self.assertIsInstance(reasons, list)
        self.assertTrue(all(isinstance(r, str) for r in reasons))

    def test_perfect_match_nears_the_ceiling(self):
        score, _ = score_song(PROFILE, make_song())
        self.assertGreater(score, 0.95 * max_score("balanced"))

    def test_genre_match_is_worth_more_than_mood_match(self):
        genre_only, _ = score_song(PROFILE, make_song(mood="intense"))
        mood_only, _ = score_song(PROFILE, make_song(genre="rock"))
        self.assertGreater(genre_only, mood_only)

    def test_a_genre_match_beats_any_single_numerical_feature(self):
        # Being exactly on-tempo must not out-rank matching the user's genre.
        on_tempo, _ = score_song(PROFILE, make_song(genre="polka", mood="sad"))
        off_tempo, _ = score_song(PROFILE, make_song(tempo_bpm=400))
        self.assertGreater(off_tempo, on_tempo)

    def test_energy_credit_is_symmetric(self):
        """0.60 and 1.00 are both 0.20 away from a 0.80 target -> equal credit."""
        low, _ = score_song(PROFILE, make_song(energy=0.60))
        high, _ = score_song(PROFILE, make_song(energy=1.00))
        self.assertAlmostEqual(low, high, places=6)

    def test_energy_too_high_is_not_rewarded(self):
        # Guards against an accidental 'bigger is better' implementation.
        closer, _ = score_song(PROFILE, make_song(energy=0.80))
        too_hot, _ = score_song(PROFILE, make_song(energy=0.99))
        self.assertGreater(closer, too_hot)

    def test_score_never_exceeds_the_ceiling(self):
        for mode in SCORING_MODES:
            score, _ = score_song(PROFILE, make_song(), mode=mode)
            self.assertLessEqual(score, max_score(mode) + 1e-9, mode)

    def test_reasons_mention_the_points_awarded(self):
        _, reasons = score_song(PROFILE, make_song())
        self.assertTrue(any("genre match" in r and "+2.0" in r for r in reasons))
        self.assertTrue(any("mood match" in r for r in reasons))

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            score_song(PROFILE, make_song(), mode="nonsense")

    def test_missing_preferences_do_not_crash(self):
        score, reasons = score_song({}, make_song())
        self.assertEqual(score, 0.0)
        self.assertEqual(reasons, [])

class TestRecommendSongs(unittest.TestCase):
    def setUp(self):
        self.songs = load_songs()

    def test_returns_k_results(self):
        self.assertEqual(len(recommend_songs(PROFILE, self.songs, k=5)), 5)

    def test_results_are_sorted_high_to_low(self):
        results = recommend_songs(PROFILE, self.songs, k=8, diversify=False)
        scores = [r["final_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_k_larger_than_catalog_is_safe(self):
        self.assertEqual(len(recommend_songs(PROFILE, self.songs, k=500)), len(self.songs))

    def test_every_result_carries_reasons(self):
        for item in recommend_songs(PROFILE, self.songs, k=5):
            self.assertTrue(item["reasons"])

    def test_diversity_changes_or_preserves_but_never_inflates_scores(self):
        for item in recommend_songs(PROFILE, self.songs, k=5):
            self.assertLessEqual(item["final_score"], item["score"] + 1e-9)

    def test_best_song_for_a_profile_is_actually_topical(self):
        results = recommend_songs(PROFILE, self.songs, k=1)
        top = results[0]["song"]
        self.assertEqual(top["genre"], "pop")
        self.assertEqual(top["mood"], "happy")

    def test_two_opposite_profiles_mostly_disagree(self):
        pop = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
        lofi = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.2}
        pop_top = [r["song"]["title"] for r in recommend_songs(pop, self.songs, k=5)]
        lofi_top = [r["song"]["title"] for r in recommend_songs(lofi, self.songs, k=5)]
        self.assertLess(len(set(pop_top) & set(lofi_top)), 3)

    def test_scoring_does_not_mutate_the_catalog(self):
        before = [dict(s) for s in self.songs]
        recommend_songs(PROFILE, self.songs, k=5)
        self.assertEqual(before, self.songs)

class TestKnownBias(unittest.TestCase):
    """These tests lock in the weaknesses we found, so a fix is visible as a failure."""

    def test_mood_can_be_outvoted_by_the_energy_cluster(self):
        """A user asking for sad + high energy gets hype songs, not sad songs."""
        songs = load_songs()
        conflicted = {
            "favorite_genre": "pop", "favorite_mood": "sad", "target_energy": 0.92,
            "target_tempo_bpm": 128, "target_danceability": 0.90,
        }
        ranking = recommend_songs(conflicted, songs, k=18)
        top = ranking[0]["song"]
        sad_position = next(
            i for i, r in enumerate(ranking, 1) if r["song"]["mood"] == "sad"
        )
        self.assertNotEqual(top["mood"], "sad")
        self.assertGreater(sad_position, 5, "if fixed, the sad song should now rank higher")

    def test_genre_label_outweighs_acoustic_texture(self):
        """An 'EDM but acoustic' listener still gets the loudest EDM track."""
        songs = load_songs()
        odd = {
            "favorite_genre": "edm", "favorite_mood": "chill", "target_energy": 0.95,
            "target_acousticness": 0.9,
        }
        top = recommend_songs(odd, songs, k=1)[0]["song"]
        self.assertEqual(top["genre"], "edm")
        self.assertLess(top["acousticness"], 0.2)

if __name__ == "__main__":
    unittest.main(verbosity=2)