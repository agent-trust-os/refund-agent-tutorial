# repositories

Small functions that read and write the database, grouped by table: `tickets.py`, `orders.py` (orders and
customers) and `records.py` (refunds, emails and the action log). Each takes the database session first and
returns plain dicts, so nothing outside this folder needs to know SQLAlchemy.
