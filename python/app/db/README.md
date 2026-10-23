# db

The database. `models.py` defines the six tables, `session.py` connects to DATABASE_URL and brings the tables
up to date with Alembic, and `seed.py` holds the starting data (3 customers, 4 orders, 5 tickets) and
`reset_database()`. SQLite is the default, so nothing needs installing; Docker uses Postgres. To change a
table, edit `models.py`, then add a migration with `uv run alembic revision --autogenerate -m "..."`.
