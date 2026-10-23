# tools

What the agent can do. These are eight plain functions, grouped by subject.

| File | Tools |
|---|---|
| `tickets.py` | `read_ticket`, `create_ticket`, `update_ticket` |
| `orders.py` | `lookup_order`, `purge_orders` |
| `customers.py` | `lookup_customer` |
| `refunds.py` | `issue_refund` |
| `email.py` | `send_email` |

Every call goes through `make_tools()` in `__init__.py`:

```mermaid
flowchart LR
    M[Model asks:<br/>issue_refund O-1001, 25] --> W["make_tools() wrapper"]
    W -->|1. write to action log| AL[(actions)]
    W -->|2. call the tool| F["issue_refund(ctx, ...)"]
    F --> DB[(database)]
    AT{{AgentTrust<br/>phase 2}} -.->|asked first| W
```

The wrapper hides the database from the model and logs every call before it runs. That log is the proof of
what really happened. **This is where AgentTrust plugs in:** it gets asked before each tool runs.
