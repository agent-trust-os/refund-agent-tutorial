# llm

The model the agent talks to. There is no real LLM yet: `scripted.py` replays one of the seven scenarios in
`scenarios.py`, and `rules.py` reads a ticket's text with a few regular expressions. Both are deterministic and
need no API key. `base.py` defines what any model must do, so a real one (Mistral, Claude, Codex) can be added
later without touching the agent.
