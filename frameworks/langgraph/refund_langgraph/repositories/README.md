# repositories

Small functions that read and write the database. Each takes a session and returns plain dicts, so nothing
outside this folder needs SQLAlchemy.

| File | Tables |
|---|---|
| `tickets.py` | tickets |
| `orders.py` | orders, customers |
| `records.py` | refunds, emails, actions (the log) |
