# app

The Refund Bot. A customer writes a ticket; the agent reads it, looks up the order and the customer, refunds,
emails, and marks the ticket resolved or escalated. Start reading at `agents/support_agent.py` (the loop) and
`tools/` (what the agent can do). `main.py` is the web app and `cli.py` is the `refund-bot` command.
