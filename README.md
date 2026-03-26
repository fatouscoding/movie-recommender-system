# Movie Recommender System

## Overview
Built a Python-based movie recommendation system that processes structured datasets of user ratings and movie metadata to generate personalized recommendations, genre trends, and popularity rankings — using Python's standard library only, no external dependencies.

---

## Features
- Top N Movies by Average Rating  
- Top Movies Within a Genre  
- Genre Popularity (based on average of movie-average ratings)
- User’s Most Preferred Genre  
- Personalized Movie Recommendations  
- Command-Line Interface (CLI) for interactive testing  

---

## Tech Stack
- Python 3.12  
- Standard Library Only (no external dependencies)  
- File I/O & Data Parsing  
- Algorithmic Sorting & Ranking  

---

## Key Implementation Details
- Robust file parsing with validation for malformed data  
- Handles edge cases such as:
  - Duplicate entries  
  - Invalid ratings  
  - Unknown movies in ratings dataset  
- Deterministic ranking system using tie-breaking rules  
- Case-sensitive and case-insensitive handling where appropriate  
- Modular function-based design (no classes)  

---

## Testing
- Automated test suite with 14 test cases  
- Covers:
  - Edge cases  
  - Tie-breaking logic  
  - Invalid input handling  
  - Recommendation correctness  
- Achieved **100% pass rate (14/14 tests)**

---

## Demo

### Top Movies by Average Rating
![Top Movies](top_movies.png)

### Personalized Recommendations
![Recommendations](recommendations.png)

---

## Sample Data

This repository includes sample input files:

- `movies.txt`
- `ratings.txt`

These can be used to test all features of the program.

---

## How to Run

1. Run the program:
```bash
python movie_recommender.py

