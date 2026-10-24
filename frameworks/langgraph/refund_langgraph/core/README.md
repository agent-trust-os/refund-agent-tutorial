# core

Settings and logging shared by the whole app.

| File | Does |
|---|---|
| `config.py` | reads `DATABASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM` from the environment |
| `logging.py` | one log line per agent step, each starting with the ticket id. Set `LOG_LEVEL=DEBUG` for more |

Find one ticket's story in the logs: `docker compose logs python | grep T-1006`.
