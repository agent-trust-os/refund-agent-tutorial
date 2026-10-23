# api

The web endpoints, one file per group in `routes/`: tickets, data (orders, customers, refunds, emails, the
action log, reset), scenarios and health. Each route checks its input with a schema and calls a service or a
repository; none of them contains business logic. With the app running, http://localhost:8000/docs lists and
tries every endpoint.
