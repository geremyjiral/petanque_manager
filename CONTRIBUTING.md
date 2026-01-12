# Contributing to Pétanque Tournament Manager

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/geremyjiral/petanque_manager.git
cd petanque_manager
```

2. **Install dependencies**
```bash
# With uv (recommended)
uv sync --all-extras

# Or with pip
pip install -e ".[dev]"
```

3. **Set up pre-commit hooks** (optional but recommended)
```bash
pip install pre-commit
pre-commit install
```

## Code Standards

### Style Guide

- Follow PEP 8 conventions
- Use type hints everywhere
- Maximum line length: 100 characters
- Use ruff for formatting and linting

### Type Checking

- All code must pass mypy strict mode
- Use explicit type annotations
- Avoid `Any` types when possible

### Documentation

- Add docstrings to all public functions, classes, and modules
- Use Google-style docstrings
- Keep README.md up to date
- Add comments for complex logic

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

- Write clean, well-documented code
- Add tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_scheduler_scoring.py
```

### 4. Lint and Format

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Type check
uv run mypy src/ app.py pages/
```

### 5. Commit Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add new scheduling constraint"
# or
git commit -m "fix: resolve terrain label generation bug"
```

Commit message prefixes:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or modifications
- `refactor:` - Code refactoring
- `style:` - Code style/formatting changes
- `chore:` - Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub with:
- Clear description of changes
- Reference to related issues
- Screenshots (if UI changes)
- Test results

## Testing Guidelines

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names
- Test edge cases and error conditions
- Aim for >80% code coverage

### Test Structure

```python
def test_feature_description() -> None:
    """Test that feature does X when Y condition."""
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_output
```

### Running Specific Tests

```bash
# Run specific test file
pytest tests/test_scheduler_scoring.py

# Run specific test function
pytest tests/test_scheduler_scoring.py::test_scheduler_generates_valid_round

# Run tests matching pattern
pytest -k "constraint"
```

## Code Review Process

1. **Self-review**: Review your own code before requesting review
2. **CI checks**: Ensure all CI checks pass
3. **Reviewer feedback**: Address all comments and questions
4. **Approval**: Get approval from at least one maintainer
5. **Merge**: Maintainer will merge your PR

## Areas for Contribution

### High Priority

- [ ] Additional constraint types (e.g., player rest time)
- [ ] Export/import tournament data
- [ ] Mobile UI improvements
- [ ] Performance optimization for large tournaments (100+ players)

### Features

- [ ] Tournament templates
- [ ] Player statistics visualizations (charts)
- [ ] Email notifications
- [ ] Multi-language support
- [ ] Print-friendly schedule views

### Documentation

- [ ] Video tutorials
- [ ] Example tournaments
- [ ] Architecture documentation
- [ ] API documentation (if we add an API)

### Testing

- [ ] Integration tests
- [ ] Storage backend tests
- [ ] UI/E2E tests with Playwright

## Questions?

- Open an issue for discussion
- Join our community chat (if available)
- Email maintainers (see README)

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on what's best for the project

Thank you for contributing! 🎯
