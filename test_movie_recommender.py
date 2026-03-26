from __future__ import annotations

import os
import tempfile
from typing import Any, Callable, Dict, List, Tuple

import movie_recommender as mr


def write_text_file(path: str, contents: str) -> None:
    """Write contents to a text file using UTF-8."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)


def run_test(name: str, fn: Callable[[], None]) -> Tuple[bool, str]:
    """Run one test and return (passed, message)."""
    try:
        fn()
        return True, "PASS"
    except AssertionError as e:
        return False, f"FAIL: {e}"
    except Exception as e:
        return False, f"ERROR: {type(e).__name__}: {e}"


def assert_equal(actual: Any, expected: Any, msg: str = "") -> None:
    """Assert actual == expected with a helpful message."""
    if actual != expected:
        prefix = f"{msg} - " if msg else ""
        raise AssertionError(f"{prefix}Expected {expected!r}, got {actual!r}")


def assert_true(cond: bool, msg: str) -> None:
    """Assert condition is True."""
    if not cond:
        raise AssertionError(msg)


def build_test_files(tmpdir: str) -> Tuple[str, str]:
    """
    Create movies and ratings test files.

    Design goals:
    - Include malformed rows
    - Include duplicate movie_id
    - Include unknown movie rating row (reported as unmatched)
    - Include duplicate (user_id, movie_name) rating row (keep first)
    - Include ties in average ratings to validate deterministic tie-breaking by name/id
    - Keep movie names case-sensitive (ratings must match movies exactly, aside from whitespace)
    - Genres are tested case-insensitively through normalize_genre()
    """
    movies_path = os.path.join(tmpdir, "movies.txt")
    ratings_path = os.path.join(tmpdir, "ratings.txt")

    movies_contents = "\n".join(
        [
            "Action|M1|Alpha",
            "Action|M2|Beta",
            "Action|M3|Gamma",
            "Drama|M4|Delta",
            "Drama|M5|Epsilon",
            "SciFi|M6|Zeta",
            "SciFi|M7|Eta",
            "SciFi|M8|Theta",
            "Action|M1|Alpha Duplicate ID",
            "BadRowNoDelimiters",
            "Too|Many|Fields|Here",
            "Action||NoId",
            "|M10|NoGenre",
            "Action|M11|",
            "",
        ]
    ) + "\n"

    ratings_contents = "\n".join(
        [
            "  Alpha  |5|U1",
            "Alpha|1|U1",
            "Gamma|4|U1",
            "Zeta|4|U1",
            "Delta|2|U1",
            "Epsilon|1|U1",
            "Beta|4.5|U3",
            "Alpha|4|U3",
            "Gamma|4|U3",
            "Zeta|4|U3",
            "Eta|4|U4",
            "Eta|4|U5",
            "Theta|4.2|U2",
            "Delta|5|U2",
            "Unknown Movie|3|U1",
            "BadRowNoDelimiters",
            "Too|Many|Fields|Here",
            "NoUser|3|",
            "NoMovie||U1",
            "Alpha|notanumber|U1",
            "Alpha|6|U1",
            "",
        ]
    ) + "\n"

    write_text_file(movies_path, movies_contents)
    write_text_file(ratings_path, ratings_contents)
    return movies_path, ratings_path


def load_all(movies_path: str, ratings_path: str) -> Dict[str, Any]:
    """Load movies and ratings and compute indexes/stats for tests."""
    movies_by_id, m_err = mr.parse_movies_file(movies_path)
    ratings, r_err = mr.parse_ratings_file(ratings_path)
    idx = mr.build_indexes(movies_by_id, ratings)
    movie_stats = mr.compute_movie_stats(idx)
    genre_stats = mr.compute_genre_stats(movies_by_id, movie_stats)
    return {
        "movies_by_id": movies_by_id,
        "ratings": ratings,
        "m_err": m_err,
        "r_err": r_err,
        "idx": idx,
        "movie_stats": movie_stats,
        "genre_stats": genre_stats,
    }


def test_01_movies_parsing_counts_and_errors() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        movies_by_id = data["movies_by_id"]
        m_err = data["m_err"]

        assert_equal(len(movies_by_id), 8, "Movies valid count")

        joined = "\n".join(m_err)
        assert_true("duplicate movie_id" in joined, "Expected duplicate movie_id error")
        assert_true("expected 3 fields" in joined, "Expected malformed field-count error")


def test_02_ratings_parsing_counts_and_errors() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        ratings = data["ratings"]
        r_err = data["r_err"]

        assert_equal(len(ratings), 14, "Ratings valid count")

        joined = "\n".join(r_err)
        assert_true("duplicate rating" in joined, "Expected duplicate (user,movie) rating error")
        assert_true("not a number" in joined, "Expected non-numeric rating error")
        assert_true("out of range" in joined, "Expected out-of-range rating error")
        assert_true("expected 3 fields" in joined, "Expected malformed field-count error")


def test_03_unmatched_ratings_unknown_movie() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        unmatched = data["idx"]["unmatched_ratings_errors"]
        assert_true(any("Unknown Movie" in s for s in unmatched), "Expected Unknown Movie in unmatched errors")


def test_04_movie_stats_alpha_average_and_count() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        idx = data["idx"]
        movie_stats = data["movie_stats"]

        alpha_id = idx["movie_id_by_name_key"][mr.normalize_movie_name("Alpha")]
        stats = movie_stats[alpha_id]
        assert_equal(stats["count"], 2, "Alpha count")
        assert_equal(stats["avg"], 4.5, "Alpha avg (no rounding expected)")


def test_05_top_movies_by_average_top3() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        rows = mr.top_movies_by_average(data["movies_by_id"], data["movie_stats"], 3)
        top_names = [r[0] for r in rows]
        assert_equal(top_names, ["Alpha", "Beta", "Theta"], "Top 3 ordering mismatch")


def test_06_movie_tie_break_name_then_id() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        rows = mr.top_movies_by_average(data["movies_by_id"], data["movie_stats"], 10)
        picked = [(name, avg, cnt) for (name, avg, cnt) in rows if avg == 4.0 and cnt == 2]
        names = [x[0] for x in picked]
        assert_equal(names, ["Eta", "Gamma", "Zeta"], "Tie-break by name should be Eta < Gamma < Zeta")


def test_07_top_movies_in_genre_case_insensitive_genre() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        rows = mr.top_movies_in_genre(data["movies_by_id"], data["movie_stats"], "acTION", 10)
        names = [r[0] for r in rows]
        assert_equal(names, ["Alpha", "Beta", "Gamma"], "Top Action movies ordering mismatch")


def test_08_genre_popularity_avg_of_movie_averages() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        rows = mr.top_genres_by_movie_average(data["genre_stats"], 3)
        genres = [r[0] for r in rows]
        assert_equal(genres, ["Action", "SciFi", "Drama"], "Genre ranking mismatch")
        assert_equal(rows[0][1], 13.0 / 3.0, "Action avg_of_movie_avgs exact check")


def test_09_user_top_genre_u1() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        tg = mr.user_top_genre("U1", data["movies_by_id"], data["idx"])
        assert_equal(tg, "Action", "U1 top genre should be Action")


def test_10_user_top_genre_u2() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        tg = mr.user_top_genre("U2", data["movies_by_id"], data["idx"])
        assert_equal(tg, "Drama", "U2 top genre should be Drama")


def test_11_recommendations_fewer_than_3_u1() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        recs = mr.recommend_movies_for_user("U1", data["movies_by_id"], data["idx"], data["movie_stats"], k=3)
        assert_equal(len(recs), 1, "U1 should have only 1 recommendation")
        assert_equal(recs[0][0], "Beta", "U1 recommendation should be Beta")


def test_12_recommendations_fewer_than_3_u2() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        recs = mr.recommend_movies_for_user("U2", data["movies_by_id"], data["idx"], data["movie_stats"], k=3)
        assert_equal(len(recs), 1, "U2 should have only 1 recommendation")
        assert_equal(recs[0][0], "Epsilon", "U2 recommendation should be Epsilon")


def test_13_user_with_no_ratings_gets_none_and_no_recs() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        tg = mr.user_top_genre("NO_SUCH_USER", data["movies_by_id"], data["idx"])
        assert_equal(tg, None, "Unknown user top genre should be None")

        recs = mr.recommend_movies_for_user(
            "NO_SUCH_USER", data["movies_by_id"], data["idx"], data["movie_stats"], k=3
        )
        assert_equal(recs, [], "Unknown user should get no recommendations")


def test_14_top_movies_in_genre_no_results() -> None:
    with tempfile.TemporaryDirectory() as td:
        movies_path, ratings_path = build_test_files(td)
        data = load_all(movies_path, ratings_path)

        rows = mr.top_movies_in_genre(data["movies_by_id"], data["movie_stats"], "Comedy", 5)
        assert_equal(rows, [], "Comedy should have no rated movies in this dataset")


def run_all_tests() -> int:
    tests: List[Tuple[str, Callable[[], None]]] = [
        ("01 Movies parsing counts and errors", test_01_movies_parsing_counts_and_errors),
        ("02 Ratings parsing counts and errors", test_02_ratings_parsing_counts_and_errors),
        ("03 Unmatched ratings (unknown movie)", test_03_unmatched_ratings_unknown_movie),
        ("04 Movie stats (Alpha avg & count)", test_04_movie_stats_alpha_average_and_count),
        ("05 Top movies by average (top 3)", test_05_top_movies_by_average_top3),
        ("06 Movie tie-break by name/id", test_06_movie_tie_break_name_then_id),
        ("07 Top movies in genre (case-insensitive genre)", test_07_top_movies_in_genre_case_insensitive_genre),
        ("08 Genre popularity (avg of movie avgs)", test_08_genre_popularity_avg_of_movie_averages),
        ("09 User top genre (U1)", test_09_user_top_genre_u1),
        ("10 User top genre (U2)", test_10_user_top_genre_u2),
        ("11 Recommendations fewer than 3 (U1)", test_11_recommendations_fewer_than_3_u1),
        ("12 Recommendations fewer than 3 (U2)", test_12_recommendations_fewer_than_3_u2),
        ("13 User with no ratings", test_13_user_with_no_ratings_gets_none_and_no_recs),
        ("14 Top movies in genre with no results", test_14_top_movies_in_genre_no_results),
    ]

    passed = 0
    failed = 0

    print("=== Running Movie Recommender Tests ===")
    for name, fn in tests:
        ok, msg = run_test(name, fn)
        print(f"{msg} - {name}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n=== Summary ===")
    print(f"Total: {len(tests)}  Passed: {passed}  Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())