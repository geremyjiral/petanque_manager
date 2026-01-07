# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-07

### Added
- Initial release of Pétanque Tournament Manager
- TRIPLETTE and DOUBLETTE tournament modes
- Smart scheduling with constraint satisfaction algorithm
- Live ranking system (wins → goal average → points for)
- Player management with role-based requirements
- SQLModel + SQLite storage (default)
- JSON file storage (fallback)
- Streamlit-based web UI with 5 pages:
  - Home: Configuration & overview
  - Players: CRUD operations with bulk import
  - Schedule: Round generation with quality grading
  - Results: Match score entry
  - Ranking: Live leaderboard with filters
- Authentication system with public viewing and admin editing
- Cookie-based sessions with streamlit-authenticator
- Comprehensive test suite (pytest)
- CI/CD pipeline with GitHub Actions
- Type checking with mypy (strict mode)
- Code formatting and linting with ruff
- Support for 4-80+ players
- Terrain labels A-Z, AA-ZZ (up to 702 terrains)
- CSV export for rankings and schedules
- Quality grading system for schedules (A+ to F)
- Reproducible scheduling with optional seed control
- Python 3.13+ support with modern type hints (PEP 604)
- uv package manager integration
- Makefile for common development tasks
- Helper script for password hashing

### Technical Details
- **Constraint Penalties**:
  - Repeated partners: 10 points
  - Repeated opponents: 5 points
  - Repeated terrains: 3 points
  - Fallback format: 4 points per player
- **Quality Grades**:
  - A+: Perfect (score = 0)
  - A: Excellent (score < 10)
  - B: Good (score < 25)
  - C: Acceptable (score < 50)
  - D: Poor (score < 100)
  - F: Very poor (score ≥ 100)
- **Ranking Algorithm**:
  1. Wins (descending)
  2. Goal average (points for - against)
  3. Points for (descending)
  4. Alphabetical name (tiebreaker)

### Dependencies
- streamlit >= 1.32.0
- pydantic >= 2.0.0, < 3.0.0
- sqlmodel >= 0.0.16
- streamlit-authenticator >= 0.3.1
- pyyaml >= 6.0
- pandas >= 2.0.0
- bcrypt >= 4.1.0

### Development Dependencies
- pytest >= 8.0.0
- pytest-cov >= 4.1.0
- mypy >= 1.8.0
- ruff >= 0.3.0
- pandas-stubs >= 2.0.0
- types-pyyaml >= 6.0.0

[0.1.0]: https://github.com/yourusername/petanque-papa/releases/tag/v0.1.0
