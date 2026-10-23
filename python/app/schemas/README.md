# schemas

The shapes of what the API accepts and returns, as Pydantic models. FastAPI uses them to reject bad input and
to build the `/docs` page.

| File | Shapes |
|---|---|
| `tickets.py` | `TicketIn` (what a customer sends), `Ticket`, `RunResultOut` (what the agent did) |
| `data.py` | `Order`, `Customer`, `Refund`, `Email`, `Action`, `ScenarioInfo` |
