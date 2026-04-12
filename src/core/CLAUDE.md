# Team: Core

## Responsibility
Shared models, configuration, database, and utilities used by all other teams.

## Scope
- Data models (`Trend`, `Post`, `PostResult`, `PostMetrics`)
- Configuration management (API keys, feature flags)
- Database layer (SQLite for local storage)
- Logging setup
- Shared HTTP client setup

## Interface
- All shared models in `models.py`
- Config via `config.py` (reads from `.env`)
- DB access via `db.py`

## Conventions
- Use Pydantic for all data models
- Use python-dotenv for env management
- Keep this package dependency-free from other src packages (no circular imports)
