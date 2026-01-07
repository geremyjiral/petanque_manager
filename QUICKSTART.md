# Quick Start Guide

Get your pétanque tournament up and running in 5 minutes!

## 🚀 Installation

**Prerequisites:** Python 3.13+

```bash
# 1. Install uv (if not already installed)
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Install dependencies
uv sync --all-extras

# 3. Run the app
uv run streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

## 👤 First Login

**Default credentials:**
- Username: `admin`
- Password: `admin`

⚠️ Change this in production by creating `.streamlit/secrets.toml`:
```toml
[auth]
admin_username = "your_username"
admin_password = "$2b$12$YOUR_HASHED_PASSWORD"
cookie_key = "your_random_secret_key"
```

Generate password hash:
```bash
# Use the helper script
uv run python scripts/hash_password.py

# Or manually in Python
python -c "from src.infra.auth import hash_password; print(hash_password('your_password'))"
```

## 📋 5-Minute Setup

### Step 1: Configure Tournament (Home Page)
- Login with admin credentials
- Select mode: **TRIPLETTE** or **DOUBLETTE**
- Set number of rounds: `3`
- Set number of terrains: `8`
- Click **Save Configuration**

### Step 2: Add Players (Players Page)
For **TRIPLETTE mode** with 12 players:
- 4 TIREUR
- 4 POINTEUR
- 4 MILIEU

For **DOUBLETTE mode** with 8 players:
- 4 TIREUR
- 4 POINTEUR_MILIEU

**Quick add:**
1. Click "Add New Player"
2. Enter name and select role
3. Click "Add Player"
4. Repeat

**Bulk import:**
1. Create CSV file:
```csv
name,role
John Doe,TIREUR
Jane Smith,POINTEUR
Bob Wilson,MILIEU
```
2. Upload via "Bulk Import" section

### Step 3: Generate Rounds (Schedule Page)
1. Click "Generate Round"
2. Review quality report (aim for A or B grade)
3. If quality is poor, regenerate with different seed
4. Repeat for each round

### Step 4: Enter Results (Results Page)
1. Select a round
2. Enter scores for each match
3. Click "Save Score"
4. Rankings update automatically!

### Step 5: View Rankings (Ranking Page)
- See live leaderboard
- Filter by role or minimum matches
- Export to CSV

## 🎯 Tournament Modes

### TRIPLETTE (3v3)
Each team needs:
- 1 TIREUR (shooter)
- 1 POINTEUR (pointer)
- 1 MILIEU (middle player)

### DOUBLETTE (2v2)
Each team needs:
- 1 TIREUR (shooter)
- 1 POINTEUR_MILIEU (pointer/middle)

## 💡 Pro Tips

### Getting Quality Schedules
- Use the seed option for reproducibility
- Regenerate if quality grade is below B
- More terrains = better scheduling flexibility

### Player Management
- Keep role balance (app shows requirements)
- Mark inactive players rather than deleting
- Use bulk import for faster setup

### Result Entry
- Use Tab key to move between score inputs
- Complete rounds sequentially for better organization
- Results update rankings immediately

### Rankings
- Primary ranking: Wins
- Tiebreaker: Goal average (points for - against)
- Use filters to compare similar players

## 🐛 Common Issues

**"Need at least 4 active players"**
→ Add more players on Players page

**"Role counts don't match"**
→ Check role requirements on home page, add needed roles

**Schedule quality is poor**
→ Try different seed or adjust player count

**Can't login**
→ Check secrets in `.streamlit/secrets.toml`

## 📚 Next Steps

- Read full [README.md](README.md) for detailed documentation
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Run tests: `uv run pytest`
- Deploy to Streamlit Cloud (see README)

## 🎮 Example Tournament

**12-Player Triplette Tournament**

```
Configuration:
- Mode: TRIPLETTE
- Rounds: 3
- Terrains: 8

Players:
- 4 TIREUR: Alice, Bob, Carol, Dave
- 4 POINTEUR: Emma, Frank, Grace, Henry
- 4 MILIEU: Ivan, Julia, Kevin, Laura

Result:
- 2 matches per round
- 6 total matches
- All players play once per round
```

## 🆘 Get Help

- Check [README.md](README.md) troubleshooting section
- Open GitHub issue
- Review example configurations above

## ⚡ Quick Commands

Using the provided `Makefile` for common tasks:

```bash
make help          # Show all available commands
make dev           # Install all dependencies
make run           # Run the application
make test          # Run tests
make test-cov      # Run tests with coverage
make lint          # Check code style
make format        # Format code
make typecheck     # Run type checking
make check         # Run all checks (lint, format, type, test)
make clean         # Clean generated files
```

Or use `uv` directly:

```bash
uv sync --all-extras              # Install dependencies
uv run streamlit run app.py       # Run app
uv run pytest                     # Run tests
uv run ruff check .               # Lint
uv run ruff format .              # Format
uv run mypy src/ app.py pages/    # Type check
```

---

**Ready to start?** Run `make run` or `uv run streamlit run app.py` and let's play! 🎯
