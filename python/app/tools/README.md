# tools

What the agent can do: eight plain functions, one file per subject (tickets, orders, customers, refunds, email).
Each takes a `ToolContext` first (the database and the ticket being worked on) and returns a dict. `make_tools`
in `__init__.py` hides that context from the model and writes every call to the action log before it runs.
This is where AgentTrust is added: in phase 2 each tool is wrapped so AgentTrust is asked before it runs.
