[![ka](https://img.shields.io/badge/lang-pt--br-green.svg)]()

# BotaaS-Server# BotaaS Server

Backend server for Bot as a Service (BotaaS) built with FastAPI.

## Requirements

- Python 3.12+
- Poetry for dependency management
- PostgreSQL 

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/nkesh20/BotaaS-Server.git
cd BotaaS-Server
```

### 2. Install dependencies

```bash
poetry install
```

### 3. Set up environment variables

Modify .env file if needed

### 4. Initialize the database

```bash
poetry run python -m app.db.init_db
```

### 5. Database migrations (Alembic)

To apply the latest database migrations:

```bash
poetry run alembic upgrade head
```

To create a new migration after changing models:

```bash
poetry run alembic revision --autogenerate -m "your message here"
```

If you encounter import errors with Alembic, ensure your `alembic/env.py` adds the project root to `sys.path`:

```python
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

## Running the server

### Development mode

```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

### Using Docker

```bash
docker-compose up -d backend
```

## API Documentation

Once the server is running, you can access:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── api/              # API endpoints
│   └── endpoints/    # Route definitions
├── core/             # Core application configuration
├── db/               # Database setup and session management
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic models (schemas)
└── services/         # Business logic
tests/
├── api/              # API tests
└── unit/             # Unit tests
```

## Running Tests

```bash
poetry run pytest
```

## License

[MIT](LICENSE)