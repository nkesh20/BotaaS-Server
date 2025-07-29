[![en](https://img.shields.io/badge/lang-en-blue.svg)](https://github.com/nkesh20/BotaaS-Server/blob/readme/README.md)

# BotaaS-Server# BotaaS სერვერი

Bot as a Service (BotaaS) ბექენდ სერვერი, რომელიც აგებულია FastAPI-სთან.

## მოთხოვნები

- Python 3.12+
- Poetry დამოკიდებულებების მართვისთვის
- PostgreSQL 

## ინსტალაცია

### 1. რეპოზიტორიის კლონირება

```bash
git clone https://github.com/nkesh20/BotaaS-Server.git
cd BotaaS-Server
```

### 2. დამოკიდებულებების ინსტალაცია

```bash
poetry install
```

### 3. გარემოს ცვლადების დაყენება

საჭიროების შემთხვევაში შეცვალეთ .env ფაილი

### 4. ბაზის ინიციალიზაცია

```bash
poetry run python -m app.db.init_db
```

### 5. ბაზის მიგრაციები (Alembic)

ბოლო ბაზის მიგრაციების გამოსაყენებლად:

```bash
poetry run alembic upgrade head
```

მოდელების შეცვლის შემდეგ ახალი მიგრაციის შესაქმნელად:

```bash
poetry run alembic revision --autogenerate -m "თქვენი შეტყობინება აქ"
```

თუ Alembic-თან იმპორტის შეცდომებს შეხვდებით, დარწმუნდით, რომ თქვენი `alembic/env.py` ამატებს პროექტის root-ს `sys.path`-ში:

```python
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

## სერვერის გაშვება

### განვითარების რეჟიმი

```bash
poetry run uvicorn app.main:app --reload
```

API იქნება ხელმისაწვდომი http://localhost:8000-ზე.

### Docker-ის გამოყენება

```bash
docker-compose up -d backend
```

## API დოკუმენტაცია

სერვერის გაშვების შემდეგ, შეგიძლიათ წვდომა:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## პროექტის სტრუქტურა

```
app/
├── api/              # API endpoints
│   └── endpoints/    # მარშრუტების განსაზღვრები
├── core/             # ძირითადი აპლიკაციის კონფიგურაცია
├── db/               # ბაზის დაყენება და სესიების მართვა
├── models/           # SQLAlchemy ORM მოდელები
├── schemas/          # Pydantic მოდელები (schemas)
└── services/         # ბიზნეს ლოგიკა
tests/
├── api/              # API ტესტები
└── unit/             # ერთეული ტესტები
```

## ტესტების გაშვება

```bash
poetry run pytest
```

## ლიცენზია

[MIT](LICENSE)