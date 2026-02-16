# 🎯 Pétanque Tournament Manager

A production-quality **Streamlit** application for managing pétanque tournaments with intelligent scheduling, live rankings, and constraint satisfaction algorithms.

[![CI](https://github.com/geremyjiral/petanque_manager/actions/workflows/ci.yml/badge.svg)](https://github.com/geremyjiral/petanque_manager/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

## ✨ Features

### 🎮 Tournament Modes
- **TRIPLETTE Mode**: 3 players per team (1 Tireur, 1 Pointeur, 1 Milieu)
- **DOUBLETTE Mode**: 2 players per team (1 Tireur, 1 Pointeur/Milieu)
- Automatic fallback to alternative formats when player counts don't divide evenly

### 📋 Player Management
- Register players with specific roles (TIREUR, POINTEUR, MILIEU, POINTEUR_MILIEU)
- Live role requirement calculator shows needed player counts
- Active/inactive player status
- Bulk import from CSV
- Player search and filtering

### 🧠 Smart Scheduling
- **Constraint satisfaction algorithm** minimizes:
  - Repeated partners (strong penalty)
  - Repeated opponents (medium penalty)
  - Repeated terrain assignments (medium penalty)
  - Fallback format usage (medium penalty)
- Quality grading system (A+ to F) for generated schedules
- Support for 4-80+ players

### 📊 Live Rankings
- Real-time leaderboard based on:
  1. Wins (descending)
  2. Goal average (points for - points against)
  3. Points for (descending)
- Role-based rankings
- Player statistics: matches played, wins, losses, win rate, goal average
- Head-to-head and partnership statistics
- CSV export

### 🔒 Security & Access Control
- **Public viewing**: Anyone can see schedules, results, and rankings
- **Admin editing**: Authentication required for:
  - Player management (add, edit, delete)
  - Round generation
  - Result entry
- Cookie-based authentication with `streamlit-authenticator`

### 💾 Flexible Storage
- **SQLModel + SQLite** (default): Robust database with migrations
- **JSON fallback**: File-based storage for simple deployments
- Switchable via configuration

## 🚀 Quick Start

### Prerequisites
- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/geremyjiral/petanque_manager.git
cd petanque_manager
```

2. **Install uv (if not already installed)**
```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

3. **Install project dependencies**
```bash
# Install all dependencies (including dev)
uv sync --all-extras

# Install only production dependencies
uv sync
```

4. **Run the application**
```bash
uv run streamlit run app.py
```

5. **Access the app**

Open your browser to [http://localhost:8501](http://localhost:8501)

### Default Credentials

For development, default admin credentials are:
- **Username**: `admin`
- **Password**: `admin`

⚠️ **Change these in production!** (See Configuration section below)

## 📦 Project Structure

```
petanque_manager/
├── app.py                      # Main Streamlit entry point
├── pages/                      # Streamlit pages
│   ├── 1_Dashboard.py         # Tournament overview
│   ├── 2_Players.py           # Player management
│   ├── 3_Schedule.py          # Round generation
│   ├── 4_Results.py           # Result entry
│   └── 5_Ranking.py           # Player rankings
├── src/
│   ├── core/                  # Business logic
│   │   ├── models.py         # Pydantic domain models
│   │   ├── scheduler.py      # Constraint satisfaction
│   │   └── stats.py          # Ranking calculations
│   ├── infra/                 # Infrastructure layer
│   │   ├── storage.py        # Abstract storage interface
│   │   ├── storage_sqlmodel.py  # SQLite implementation
│   │   ├── storage_json.py   # JSON implementation
│   │   └── auth.py           # Authentication
│   └── utils/                 # Utilities
│       ├── terrain_labels.py # A-Z, AA-ZZ generation
├── tests/                     # Test suite
│   ├── test_scheduler_scoring.py
│   ├── test_constraints_tracking.py
│   └── test_ranking.py
├── .github/workflows/         # CI/CD
│   └── ci.yml                # GitHub Actions
├── .streamlit/
│   └── config.toml           # Streamlit configuration
├── pyproject.toml            # Project metadata & dependencies
└── README.md                 # This file
```

## ⚙️ Configuration

### Streamlit Secrets

For production deployment, create `.streamlit/secrets.toml`:

```toml
# Authentication
[auth]
admin_username = "your_admin_username"
admin_password = "$2b$12$YOUR_HASHED_PASSWORD_HERE"

# Cookie encryption key
cookie_key = "your_secure_random_key_here"
```

#### Generating a Hashed Password

```python
from streamlit_authenticator.utilities import Hasher

password = "your_secure_password"
hashed = Hasher([password]).generate()[0]
print(hashed)
```

Or use the utility:

```python
from src.petanque_manager.infra.auth import hash_password

print(hash_password("your_secure_password"))
```

### Environment Variables

Alternatively, use environment variables:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` (hashed)
- `COOKIE_KEY`

### Tournament Configuration

Configure via the web UI (requires admin login):
- **Mode**: TRIPLETTE or DOUBLETTE
- **Number of Rounds**: 1-10
- **Number of Terrains**: 1-52 (A-Z, AA-ZZ)
- **Storage Backend**: SQLModel or JSON

## ☁️ Deployment

### Streamlit Community Cloud

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/geremyjiral/petanque_manager.git
git push -u origin main
```

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repository
   - Select `app.py` as the main file
   - Add secrets in the Streamlit Cloud dashboard (Settings → Secrets)

3. **Add Secrets**

In Streamlit Cloud dashboard, add:
```toml
[auth]
admin_username = "admin"
admin_password = "$2b$12$YOUR_HASHED_PASSWORD"

cookie_key = "your_secure_random_key"
```

4. **Deploy!**

Your app will be live at `https://your-app-name.streamlit.app`

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t petanque-tournament .
docker run -p 8501:8501 petanque-tournament
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_scheduler_scoring.py

# Run with verbose output
uv run pytest -v
```

### Linting & Type Checking

```bash
# Lint with ruff
uv run ruff check .

# Format with ruff
uv run ruff format .

# Type check with mypy
uv run mypy src/ app.py pages/
```

## 📖 Usage Guide

### 1. Configure Tournament

- Open the home page
- Login with admin credentials
- Set tournament mode (TRIPLETTE or DOUBLETTE)
- Configure number of rounds and terrains
- Save configuration

### 2. Add Players

- Navigate to **Players** page
- Add players one by one or bulk import from CSV
- Assign roles based on tournament mode
- Monitor role requirements (the app shows deficits in real-time)

### 3. Generate Rounds

- Navigate to **Schedule** page
- Click "Generate Round"
- Review quality report (A+ to F grade)
- Repeat for all rounds

### 4. Enter Results

- Navigate to **Results** page
- Select a round
- Enter scores for each match (first to 13 wins)
- Results update rankings immediately

### 5. View Rankings

- Navigate to **Ranking** page
- View overall standings
- Filter by role, minimum matches, or name
- Export rankings to CSV

## 🎲 Scheduling Algorithm

### Constraint Satisfaction

The scheduler uses a heuristic search algorithm that:

1. **Generates candidate schedules** by forming teams with correct role compositions
2. **Scores each schedule** based on constraint violations
4. **Returns the schedule with the lowest penalty score**

### Penalty Weights

- **Repeated partners**: 10 points per pair
- **Repeated opponents**: 5 points per pair
- **Repeated terrain**: 3 points per player
- **Fallback format**: 4 points per player

### Quality Grades

- **A+**: Perfect (score = 0)
- **A**: Excellent (score < 10)
- **B**: Good (score < 25)
- **C**: Acceptable (score < 50)
- **D**: Poor (score < 100)
- **F**: Very poor (score ≥ 100)

## 🔧 Troubleshooting

### Issue: "Need at least 4 active players"

**Solution**: Add more players on the Players page. Minimum is 4 players.

### Issue: "Role counts don't match requirements"

**Solution**: Check the role requirements on the home page. Add players with the needed roles. The app will use fallback formats if needed.

### Issue: Database locked (SQLite)

**Solution**:
- Ensure only one instance is writing at a time
- Switch to JSON storage backend in configuration
- Or use a proper database (PostgreSQL) for production with multiple writers

### Issue: Authentication not working

**Solution**:
- Verify secrets are set correctly in `.streamlit/secrets.toml` or Streamlit Cloud
- Ensure password is properly hashed
- Clear browser cookies and try again

### Issue: Streamlit Cloud deployment fails

**Solution**:
- Check that `pyproject.toml` has all dependencies
- Ensure Python version is 3.11+ in `pyproject.toml`
- Verify secrets are added in Streamlit Cloud dashboard
- Check deployment logs for specific errors

## 📝 Data Persistence

### SQLModel (Default)

- Data stored in `tournament.db` SQLite file
- Automatically creates tables on first run
- Survives app restarts
- Suitable for single-writer scenarios

### JSON (Fallback)

- Data stored in `tournament_data.json`
- Human-readable format
- Good for debugging
- Suitable for low-concurrency scenarios

⚠️ **Backup your data regularly!** Both SQLite and JSON files should be backed up.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest`, `ruff check`, `mypy`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Powered by [Pydantic](https://pydantic.dev/) and [SQLModel](https://sqlmodel.tiangolo.com/)
- Authentication via [streamlit-authenticator](https://github.com/mkhorasani/Streamlit-Authenticator)
- Type checking with [mypy](http://mypy-lang.org/)
- Linting with [ruff](https://github.com/astral-sh/ruff)

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/geremyjiral/petanque_manager/issues)
- Check the [troubleshooting section](#-troubleshooting)

---

Made with ❤️ for pétanque enthusiasts | 🎯 Bonjour Papa!
