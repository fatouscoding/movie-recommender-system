from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple


def normalize_genre(text: str) -> str:
    """Normalize a genre for case-insensitive matching (strip + collapse spaces + casefold)."""
    parts = text.strip().split()
    return " ".join(parts).casefold()


def normalize_movie_name(text: str) -> str:
    """Normalize a movie name preserving case (strip + collapse spaces)."""
    parts = text.strip().split()
    return " ".join(parts)


def parse_int(text: str) -> Optional[int]:
    """Parse an integer from text; return None if parsing fails."""
    try:
        return int(text)
    except ValueError:
        return None


def parse_rating(text: str) -> Optional[float]:
    """Parse a rating number from text; return None if parsing fails."""
    try:
        return float(text)
    except ValueError:
        return None


def format_float(value: float) -> str:
    """Format a float for printing without rounding computed values."""
    return str(value)


def safe_input(prompt: str) -> str:
    """Read user input and return stripped text."""
    return input(prompt).strip()


def validate_movie_row(line: str, line_no: int) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """
    Validate one movies file line: movie_genre|movie_id|movie_name.

    Returns (movie_dict, error_message). movie_dict is None if invalid.
    Blank/whitespace-only lines return (None, None) and are ignored.
    """
    raw = line.rstrip("\n")
    if raw.strip() == "":
        return None, None

    parts = raw.split("|")
    if len(parts) != 3:
        return None, f"Line {line_no}: expected 3 fields separated by '|', got {len(parts)}"

    genre = parts[0].strip()
    movie_id = parts[1].strip()
    movie_name = parts[2].strip()

    if not genre or not movie_id or not movie_name:
        return None, f"Line {line_no}: genre, movie_id, and movie_name must all be non-empty"

    return {
        "genre": genre,
        "movie_id": movie_id,
        "movie_name": movie_name,
        "name_key": normalize_movie_name(movie_name),
        "genre_key": normalize_genre(genre),
    }, None


def validate_rating_row(line: str, line_no: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate one ratings file line: movie_name|rating|user_id.

    Rating must be numeric and within [0, 5] inclusive.
    Returns (rating_dict, error_message). rating_dict is None if invalid.
    Blank/whitespace-only lines return (None, None) and are ignored.
    """
    raw = line.rstrip("\n")
    if raw.strip() == "":
        return None, None

    parts = raw.split("|")
    if len(parts) != 3:
        return None, f"Line {line_no}: expected 3 fields separated by '|', got {len(parts)}"

    movie_name_raw = parts[0].strip()
    rating_text = parts[1].strip()
    user_id = parts[2].strip()

    if not movie_name_raw or not rating_text or not user_id:
        return None, f"Line {line_no}: movie_name, rating, and user_id must all be non-empty"

    rating_val = parse_rating(rating_text)
    if rating_val is None:
        return None, f"Line {line_no}: rating '{rating_text}' is not a number"

    if rating_val < 0 or rating_val > 5:
        return None, f"Line {line_no}: rating {rating_val} is out of range [0, 5]"

    return {
        "movie_name_raw": movie_name_raw,
        "movie_name_key": normalize_movie_name(movie_name_raw),
        "rating": float(rating_val),
        "user_id": user_id,
        "line_no": line_no,
    }, None


def parse_movies_file(path: str) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    """
    Parse a movies file into movies_by_id with robust per-line validation.

    Returns (movies_by_id, errors).

    Duplicate policies:
    - Duplicate movie_id: keep the first occurrence, reject later duplicates.
    - Duplicate movie_name key (case-preserving normalized): reject later duplicates to avoid ambiguity.
    """
    movies_by_id: Dict[str, Dict[str, str]] = {}
    errors: List[str] = []
    movie_id_by_name_key: Dict[str, str] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                movie, err = validate_movie_row(line, i)
                if err:
                    errors.append(f"{path}: {err}")
                    continue
                if movie is None:
                    continue

                movie_id = movie["movie_id"]
                name_key = movie["name_key"]

                if movie_id in movies_by_id:
                    errors.append(f"{path}: Line {i}: duplicate movie_id '{movie_id}' (kept first)")
                    continue

                if name_key in movie_id_by_name_key:
                    prev_id = movie_id_by_name_key[name_key]
                    errors.append(
                        f"{path}: Line {i}: duplicate movie_name '{movie['movie_name']}' "
                        f"(matches existing movie_id '{prev_id}'); rejected to avoid ambiguity"
                    )
                    continue

                movies_by_id[movie_id] = movie
                movie_id_by_name_key[name_key] = movie_id

    except OSError as e:
        errors.append(f"{path}: could not open file ({e})")

    return movies_by_id, errors


def parse_ratings_file(path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse a ratings file into a list of ratings with robust per-line validation.

    Returns (ratings, errors).

    Duplicate policy:
    - Duplicate (user_id, movie_name_key) rating: keep the first occurrence, reject later duplicates.
    """
    ratings: List[Dict[str, Any]] = []
    errors: List[str] = []
    seen_user_movie: Set[Tuple[str, str]] = set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                rating, err = validate_rating_row(line, i)
                if err:
                    errors.append(f"{path}: {err}")
                    continue
                if rating is None:
                    continue

                key = (rating["user_id"], rating["movie_name_key"])
                if key in seen_user_movie:
                    errors.append(
                        f"{path}: Line {i}: duplicate rating for user_id '{rating['user_id']}' "
                        f"and movie_name '{rating['movie_name_raw']}' (kept first)"
                    )
                    continue

                seen_user_movie.add(key)
                ratings.append(rating)

    except OSError as e:
        errors.append(f"{path}: could not open file ({e})")

    return ratings, errors


def build_indexes(movies_by_id: Dict[str, Dict[str, str]], ratings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build lookup structures from movies and ratings.

    Returns a dict with:
    - movie_id_by_name_key: movie name key -> movie_id
    - ratings_by_user: user_id -> list of rating dicts (all valid rating rows)
    - ratings_by_movie_id: movie_id -> list of rating floats (only ratings that matched a movie)
    - rated_movie_ids_by_user: user_id -> set of movie_ids (only matched-to-movies)
    - unmatched_ratings_errors: list of strings for rating lines that reference unknown movies
    """
    movie_id_by_name_key: Dict[str, str] = {m["name_key"]: mid for mid, m in movies_by_id.items()}

    ratings_by_user: Dict[str, List[Dict[str, Any]]] = {}
    ratings_by_movie_id: Dict[str, List[float]] = {}
    rated_movie_ids_by_user: Dict[str, Set[str]] = {}
    unmatched_ratings_errors: List[str] = []

    for r in ratings:
        user_id = r["user_id"]
        ratings_by_user.setdefault(user_id, []).append(r)

        movie_id = movie_id_by_name_key.get(r["movie_name_key"])
        if movie_id is None:
            unmatched_ratings_errors.append(
                f"ratings: Line {r['line_no']}: unknown movie_name '{r['movie_name_raw']}'"
            )
            continue

        ratings_by_movie_id.setdefault(movie_id, []).append(float(r["rating"]))
        rated_movie_ids_by_user.setdefault(user_id, set()).add(movie_id)

    return {
        "movie_id_by_name_key": movie_id_by_name_key,
        "ratings_by_user": ratings_by_user,
        "ratings_by_movie_id": ratings_by_movie_id,
        "rated_movie_ids_by_user": rated_movie_ids_by_user,
        "unmatched_ratings_errors": unmatched_ratings_errors,
    }


def compute_movie_stats(indexes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Compute per-movie statistics from indexes.

    Returns movie_stats: movie_id -> {"sum": float, "count": int, "avg": float}.
    Averages are not rounded.
    """
    ratings_by_movie_id: Dict[str, List[float]] = indexes.get("ratings_by_movie_id", {})
    movie_stats: Dict[str, Dict[str, Any]] = {}

    for movie_id, ratings in ratings_by_movie_id.items():
        total = 0.0
        for x in ratings:
            total += x
        count = len(ratings)
        avg = total / count if count > 0 else 0.0
        movie_stats[movie_id] = {"sum": total, "count": count, "avg": avg}

    return movie_stats


def compute_genre_stats(
    movies_by_id: Dict[str, Dict[str, str]],
    movie_stats: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Compute per-genre popularity as average of movie-average ratings in that genre.

    Only includes movies that have at least 1 rating (i.e., present in movie_stats).
    Returns genre_stats: genre_key -> {"genre": str, "movie_count": int, "avg_of_movie_avgs": float}.
    """
    sum_by_genre: Dict[str, float] = {}
    count_by_genre: Dict[str, int] = {}
    display_by_genre: Dict[str, str] = {}

    for movie_id, stats in movie_stats.items():
        movie = movies_by_id.get(movie_id)
        if movie is None:
            continue
        gk = movie["genre_key"]
        sum_by_genre[gk] = sum_by_genre.get(gk, 0.0) + float(stats["avg"])
        count_by_genre[gk] = count_by_genre.get(gk, 0) + 1
        if gk not in display_by_genre:
            display_by_genre[gk] = movie["genre"]

    genre_stats: Dict[str, Dict[str, Any]] = {}
    for gk in sum_by_genre:
        movie_count = count_by_genre[gk]
        avg_of_movie_avgs = sum_by_genre[gk] / movie_count if movie_count > 0 else 0.0
        genre_stats[gk] = {
            "genre": display_by_genre.get(gk, gk),
            "movie_count": movie_count,
            "avg_of_movie_avgs": avg_of_movie_avgs,
            "genre_key": gk,
        }

    return genre_stats


def movie_sort_key(movie_name_key: str, movie_id: str, avg: float) -> Tuple[float, str, str]:
    """
    Deterministic movie ranking key.

    Sort order:
    1) higher avg (descending)
    2) movie_name_key (ascending)
    3) movie_id (ascending)
    """
    return (-avg, movie_name_key, movie_id)


def genre_sort_key(genre_key: str, avg_of_movie_avgs: float) -> Tuple[float, str]:
    """
    Deterministic genre ranking key.

    Sort order:
    1) higher avg_of_movie_avgs (descending)
    2) genre_key (ascending)
    """
    return (-avg_of_movie_avgs, genre_key)


def top_movies_by_average(
    movies_by_id: Dict[str, Dict[str, str]],
    movie_stats: Dict[str, Dict[str, Any]],
    n: int,
) -> List[Tuple[str, float, int]]:
    """
    Return top n movies by average rating.

    Only includes movies with at least 1 rating.
    Each row: (movie_name, avg, count).
    """
    rows: List[Tuple[str, float, int, str, str]] = []
    for movie_id, stats in movie_stats.items():
        movie = movies_by_id.get(movie_id)
        if movie is None:
            continue
        avg = float(stats["avg"])
        count = int(stats["count"])
        rows.append((movie["movie_name"], avg, count, movie["name_key"], movie_id))

    rows.sort(key=lambda r: movie_sort_key(r[3], r[4], r[1]))
    return [(name, avg, count) for (name, avg, count, _nk, _mid) in rows[: max(n, 0)]]


def top_movies_in_genre(
    movies_by_id: Dict[str, Dict[str, str]],
    movie_stats: Dict[str, Dict[str, Any]],
    genre: str,
    n: int,
) -> List[Tuple[str, float, int]]:
    """
    Return top n movies within a given genre by average rating.

    Genre matching is case-insensitive via normalize_genre().
    Only includes movies with at least 1 rating.
    Each row: (movie_name, avg, count).
    """
    target_gk = normalize_genre(genre)

    rows: List[Tuple[str, float, int, str, str]] = []
    for movie_id, stats in movie_stats.items():
        movie = movies_by_id.get(movie_id)
        if movie is None:
            continue
        if movie["genre_key"] != target_gk:
            continue
        avg = float(stats["avg"])
        count = int(stats["count"])
        rows.append((movie["movie_name"], avg, count, movie["name_key"], movie_id))

    rows.sort(key=lambda r: movie_sort_key(r[3], r[4], r[1]))
    return [(name, avg, count) for (name, avg, count, _nk, _mid) in rows[: max(n, 0)]]


def top_genres_by_movie_average(
    genre_stats: Dict[str, Dict[str, Any]],
    n: int,
) -> List[Tuple[str, float, int]]:
    """
    Return top n genres by average of movie-average ratings in that genre.

    Each row: (genre_display, avg_of_movie_avgs, movie_count_used).
    """
    rows: List[Tuple[str, float, int, str]] = []
    for gk, stats in genre_stats.items():
        rows.append((str(stats["genre"]), float(stats["avg_of_movie_avgs"]), int(stats["movie_count"]), gk))

    rows.sort(key=lambda r: genre_sort_key(r[3], r[1]))
    return [(genre, avg, movie_count) for (genre, avg, movie_count, _gk) in rows[: max(n, 0)]]


def user_top_genre(
    user_id: str,
    movies_by_id: Dict[str, Dict[str, str]],
    indexes: Dict[str, Any],
) -> Optional[str]:
    """
    Return the user's top genre based on the user's ratings in each genre.

    Sort order:
    1) higher average rating within the genre
    2) genre_key ascending
    Returns genre display name, or None if user has no matched ratings.
    """
    ratings_by_user: Dict[str, List[Dict[str, Any]]] = indexes.get("ratings_by_user", {})
    movie_id_by_name_key: Dict[str, str] = indexes.get("movie_id_by_name_key", {})

    user_ratings = ratings_by_user.get(user_id, [])
    if not user_ratings:
        return None

    sum_by_genre: Dict[str, float] = {}
    count_by_genre: Dict[str, int] = {}
    display_by_genre: Dict[str, str] = {}

    for r in user_ratings:
        movie_id = movie_id_by_name_key.get(r["movie_name_key"])
        if movie_id is None:
            continue
        movie = movies_by_id.get(movie_id)
        if movie is None:
            continue

        gk = movie["genre_key"]
        sum_by_genre[gk] = sum_by_genre.get(gk, 0.0) + float(r["rating"])
        count_by_genre[gk] = count_by_genre.get(gk, 0) + 1
        if gk not in display_by_genre:
            display_by_genre[gk] = movie["genre"]

    if not count_by_genre:
        return None

    rows: List[Tuple[str, float, str]] = []
    for gk in count_by_genre:
        avg = sum_by_genre[gk] / count_by_genre[gk]
        rows.append((display_by_genre.get(gk, gk), avg, gk))

    rows.sort(key=lambda r: (-r[1], r[2]))
    return rows[0][0]


def recommend_movies_for_user(
    user_id: str,
    movies_by_id: Dict[str, Dict[str, str]],
    indexes: Dict[str, Any],
    movie_stats: Dict[str, Dict[str, Any]],
    k: int = 3,
) -> List[Tuple[str, float, int]]:
    """
    Recommend up to k movies: most popular movies from user's top genre not yet rated by them.

    Popularity ranking:
    avg desc, name_key asc, movie_id asc.
    Returns rows: (movie_name, avg, count).
    """
    top_genre_display = user_top_genre(user_id, movies_by_id, indexes)
    if top_genre_display is None:
        return []

    top_gk = normalize_genre(top_genre_display)
    rated_movie_ids_by_user: Dict[str, Set[str]] = indexes.get("rated_movie_ids_by_user", {})
    already_rated = rated_movie_ids_by_user.get(user_id, set())

    candidates: List[Tuple[str, float, int, str, str]] = []
    for movie_id, stats in movie_stats.items():
        if movie_id in already_rated:
            continue
        movie = movies_by_id.get(movie_id)
        if movie is None:
            continue
        if movie["genre_key"] != top_gk:
            continue
        avg = float(stats["avg"])
        count = int(stats["count"])
        candidates.append((movie["movie_name"], avg, count, movie["name_key"], movie_id))

    candidates.sort(key=lambda r: movie_sort_key(r[3], r[4], r[1]))
    return [(name, avg, count) for (name, avg, count, _nk, _mid) in candidates[: max(k, 0)]]


def format_table(rows: List[Tuple[Any, ...]], headers: Tuple[str, ...]) -> str:
    """Return a simple aligned table string for console output."""
    str_rows: List[List[str]] = [[str(x) for x in r] for r in rows]
    str_headers = [str(h) for h in headers]

    widths = [len(h) for h in str_headers]
    for r in str_rows:
        for j, cell in enumerate(r):
            if j >= len(widths):
                widths.append(len(cell))
            else:
                widths[j] = max(widths[j], len(cell))

    def fmt_row(cells: List[str]) -> str:
        return " | ".join(cells[j].ljust(widths[j]) for j in range(len(widths)))

    lines: List[str] = []
    lines.append(fmt_row(str_headers))
    lines.append("-+-".join("-" * w for w in widths))
    for r in str_rows:
        padded = r + [""] * (len(widths) - len(r))
        lines.append(fmt_row(padded))
    return "\n".join(lines)


def print_errors(title: str, errors: List[str], max_show: int = 10) -> None:
    """Print an error summary with up to max_show examples."""
    if not errors:
        return
    print(f"\n[{title}] {len(errors)} issue(s) found.")
    for e in errors[:max_show]:
        print(f"  - {e}")
    if len(errors) > max_show:
        print(f"  ... and {len(errors) - max_show} more.")


def prompt_for_n(default_n: int = 5) -> int:
    """Prompt user for an integer n and return a safe value (>= 0)."""
    text = safe_input(f"Enter n (default {default_n}): ")
    if text == "":
        return default_n
    val = parse_int(text)
    if val is None or val < 0:
        print("Invalid n. Using 0.")
        return 0
    return val


def prompt_for_genre() -> str:
    """Prompt user for a genre string."""
    return safe_input("Enter genre: ")


def prompt_for_user_id() -> str:
    """Prompt user for a user_id string."""
    return safe_input("Enter user_id: ")


def show_menu() -> None:
    """Print the main menu."""
    print("\n=== Movie Recommender Menu ===")
    print("1) Load movies file")
    print("2) Load ratings file")
    print("3) Movie popularity: top n movies by average rating")
    print("4) Top n in a genre by average rating")
    print("5) Genre popularity: top n genres (avg of movie-average ratings)")
    print("6) User top genre")
    print("7) Recommend movies (3 from user's top genre not yet rated)")
    print("8) Show load status / data summary")
    print("0) Exit")


def summarize_state(state: Dict[str, Any]) -> None:
    """Print what is loaded and basic counts."""
    movies_by_id: Dict[str, Dict[str, str]] = state.get("movies_by_id") or {}
    ratings: List[Dict[str, Any]] = state.get("ratings") or []
    indexes: Optional[Dict[str, Any]] = state.get("indexes")
    movie_stats: Optional[Dict[str, Dict[str, Any]]] = state.get("movie_stats")
    genre_stats: Optional[Dict[str, Dict[str, Any]]] = state.get("genre_stats")

    print("\n=== Data Summary ===")
    print(f"Movies loaded:  {'yes' if state.get('movies_loaded') else 'no'} (count={len(movies_by_id)})")
    print(f"Ratings loaded: {'yes' if state.get('ratings_loaded') else 'no'} (count={len(ratings)})")

    if indexes is not None:
        unmatched = indexes.get("unmatched_ratings_errors", [])
        rated_movies = len(indexes.get("ratings_by_movie_id", {}))
        print(f"Rated movies (matched): {rated_movies}")
        print(f"Unmatched rating rows (unknown movie_name): {len(unmatched)}")
    else:
        print("Indexes: not built yet")

    if movie_stats is not None:
        print(f"Movie stats computed: yes (rated movies={len(movie_stats)})")
    else:
        print("Movie stats computed: no")

    if genre_stats is not None:
        print(f"Genre stats computed: yes (rated genres={len(genre_stats)})")
    else:
        print("Genre stats computed: no")


def ensure_indexes_and_stats(state: Dict[str, Any]) -> None:
    """Ensure indexes, movie_stats, and genre_stats are computed if possible."""
    if not state.get("movies_loaded") or not state.get("ratings_loaded"):
        state["indexes"] = None
        state["movie_stats"] = None
        state["genre_stats"] = None
        return

    movies_by_id: Dict[str, Dict[str, str]] = state["movies_by_id"]
    ratings: List[Dict[str, Any]] = state["ratings"]

    indexes = build_indexes(movies_by_id, ratings)
    state["indexes"] = indexes
    state["movie_stats"] = compute_movie_stats(indexes)
    state["genre_stats"] = compute_genre_stats(movies_by_id, state["movie_stats"])


def action_load_movies(state: Dict[str, Any]) -> None:
    """Load movies file and update state (with error reporting)."""
    path = safe_input("Enter movies file path: ")
    movies_by_id, errors = parse_movies_file(path)

    state["movies_by_id"] = movies_by_id
    state["movies_errors"] = errors
    state["movies_loaded"] = bool(movies_by_id) and (not any("could not open file" in e for e in errors))

    print(f"\nLoaded movies: {len(movies_by_id)} valid row(s).")
    print_errors("Movies parsing", errors)

    ensure_indexes_and_stats(state)


def action_load_ratings(state: Dict[str, Any]) -> None:
    """Load ratings file and update state (with error reporting)."""
    path = safe_input("Enter ratings file path: ")
    ratings, errors = parse_ratings_file(path)

    state["ratings"] = ratings
    state["ratings_errors"] = errors
    state["ratings_loaded"] = bool(ratings) and (not any("could not open file" in e for e in errors))

    print(f"\nLoaded ratings: {len(ratings)} valid row(s).")
    print_errors("Ratings parsing", errors)

    ensure_indexes_and_stats(state)

    indexes = state.get("indexes")
    if indexes is not None:
        print_errors("Ratings unmatched-to-movies", indexes.get("unmatched_ratings_errors", []))


def action_top_movies(state: Dict[str, Any]) -> None:
    """Run 'movie popularity: top n movies by average rating' and print results."""
    if not state.get("movies_loaded"):
        print("\nMovies not loaded yet. Please load movies first.")
        return
    if not state.get("ratings_loaded"):
        print("\nRatings not loaded yet. Please load ratings first.")
        return

    n = prompt_for_n(default_n=5)
    movies_by_id: Dict[str, Dict[str, str]] = state["movies_by_id"]
    movie_stats: Dict[str, Dict[str, Any]] = state["movie_stats"] or {}

    rows = top_movies_by_average(movies_by_id, movie_stats, n)
    if not rows:
        print("\nNo rated movies found.")
        return

    printable: List[Tuple[str, str, int]] = [(name, format_float(avg), count) for (name, avg, count) in rows]
    print("\nTop Movies by Average Rating")
    print(format_table(printable, ("Movie", "Average", "Count")))


def action_top_movies_in_genre(state: Dict[str, Any]) -> None:
    """Run 'top n movies in a genre by average rating' and print results."""
    if not state.get("movies_loaded"):
        print("\nMovies not loaded yet. Please load movies first.")
        return
    if not state.get("ratings_loaded"):
        print("\nRatings not loaded yet. Please load ratings first.")
        return

    genre = prompt_for_genre()
    n = prompt_for_n(default_n=5)

    movies_by_id: Dict[str, Dict[str, str]] = state["movies_by_id"]
    movie_stats: Dict[str, Dict[str, Any]] = state["movie_stats"] or {}

    rows = top_movies_in_genre(movies_by_id, movie_stats, genre, n)
    if not rows:
        print(f"\nNo rated movies found for genre '{genre}'.")
        return

    printable: List[Tuple[str, str, int]] = [(name, format_float(avg), count) for (name, avg, count) in rows]
    print(f"\nTop Movies in Genre: {genre}")
    print(format_table(printable, ("Movie", "Average", "Count")))


def action_top_genres(state: Dict[str, Any]) -> None:
    """Run 'genre popularity: top n genres' and print results."""
    if not state.get("movies_loaded"):
        print("\nMovies not loaded yet. Please load movies first.")
        return
    if not state.get("ratings_loaded"):
        print("\nRatings not loaded yet. Please load ratings first.")
        return

    n = prompt_for_n(default_n=5)
    genre_stats: Dict[str, Dict[str, Any]] = state["genre_stats"] or {}

    rows = top_genres_by_movie_average(genre_stats, n)
    if not rows:
        print("\nNo rated genres found.")
        return

    printable: List[Tuple[str, str, int]] = [
        (genre, format_float(avg), movie_count) for (genre, avg, movie_count) in rows
    ]
    print("\nTop Genres (Average of Movie Averages)")
    print(format_table(printable, ("Genre", "Avg(Movie Avgs)", "Movies Used")))


def action_user_top_genre(state: Dict[str, Any]) -> None:
    """Run 'user top genre' and print result."""
    if not state.get("movies_loaded"):
        print("\nMovies not loaded yet. Please load movies first.")
        return
    if not state.get("ratings_loaded"):
        print("\nRatings not loaded yet. Please load ratings first.")
        return

    user_id = prompt_for_user_id()
    movies_by_id: Dict[str, Dict[str, str]] = state["movies_by_id"]
    indexes: Dict[str, Any] = state.get("indexes") or {}

    result = user_top_genre(user_id, movies_by_id, indexes)
    if result is None:
        print(f"\nNo matched ratings found for user_id '{user_id}'.")
        return

    print(f"\nUser '{user_id}' top genre: {result}")


def action_recommend(state: Dict[str, Any]) -> None:
    """Run 'recommend movies' and print up to 3 recommendations."""
    if not state.get("movies_loaded"):
        print("\nMovies not loaded yet. Please load movies first.")
        return
    if not state.get("ratings_loaded"):
        print("\nRatings not loaded yet. Please load ratings first.")
        return

    user_id = prompt_for_user_id()
    movies_by_id: Dict[str, Dict[str, str]] = state["movies_by_id"]
    indexes: Dict[str, Any] = state.get("indexes") or {}
    movie_stats: Dict[str, Dict[str, Any]] = state["movie_stats"] or {}

    recs = recommend_movies_for_user(user_id, movies_by_id, indexes, movie_stats, k=3)
    if not recs:
        tg = user_top_genre(user_id, movies_by_id, indexes)
        if tg is None:
            print(f"\nCannot recommend: no matched ratings found for user_id '{user_id}'.")
        else:
            print(f"\nNo recommendations available (user top genre: {tg}).")
        return

    printable: List[Tuple[str, str, int]] = [(name, format_float(avg), count) for (name, avg, count) in recs]
    tg = user_top_genre(user_id, movies_by_id, indexes) or "(unknown)"
    print(f"\nRecommendations for user '{user_id}' (Top genre: {tg})")
    print(format_table(printable, ("Movie", "Average", "Count")))


def main(argv: List[str]) -> int:
    """
    Run the menu-driven CLI.

    Optional: if argv has movies and ratings file paths, load them at startup:
    python movie_recommender.py movies.txt ratings.txt
    """
    state: Dict[str, Any] = {
        "movies_loaded": False,
        "ratings_loaded": False,
        "movies_by_id": {},
        "ratings": [],
        "movies_errors": [],
        "ratings_errors": [],
        "indexes": None,
        "movie_stats": None,
        "genre_stats": None,
    }

    if len(argv) >= 3:
        movies_path = argv[1]
        ratings_path = argv[2]

        movies_by_id, m_err = parse_movies_file(movies_path)
        ratings, r_err = parse_ratings_file(ratings_path)

        state["movies_by_id"] = movies_by_id
        state["ratings"] = ratings
        state["movies_errors"] = m_err
        state["ratings_errors"] = r_err
        state["movies_loaded"] = bool(movies_by_id) and (not any("could not open file" in e for e in m_err))
        state["ratings_loaded"] = bool(ratings) and (not any("could not open file" in e for e in r_err))
        ensure_indexes_and_stats(state)

        print("Loaded from command-line arguments.")
        print(f"Movies: {len(movies_by_id)} valid rows. Ratings: {len(ratings)} valid rows.")
        print_errors("Movies parsing", m_err)
        print_errors("Ratings parsing", r_err)
        idx = state.get("indexes")
        if idx is not None:
            print_errors("Ratings unmatched-to-movies", idx.get("unmatched_ratings_errors", []))

    while True:
        show_menu()
        choice = safe_input("Choose an option: ")

        if choice == "1":
            action_load_movies(state)
        elif choice == "2":
            action_load_ratings(state)
        elif choice == "3":
            action_top_movies(state)
        elif choice == "4":
            action_top_movies_in_genre(state)
        elif choice == "5":
            action_top_genres(state)
        elif choice == "6":
            action_user_top_genre(state)
        elif choice == "7":
            action_recommend(state)
        elif choice == "8":
            summarize_state(state)
            print_errors("Movies parsing", state.get("movies_errors", []))
            print_errors("Ratings parsing", state.get("ratings_errors", []))
            idx = state.get("indexes")
            if idx is not None:
                print_errors("Ratings unmatched-to-movies", idx.get("unmatched_ratings_errors", []))
        elif choice == "0":
            print("Goodbye.")
            return 0
        else:
            print("Invalid choice. Please select a menu option number.")

    # unreachable
    # return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))