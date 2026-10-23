# agents

The agent itself. `support_agent.py` is the loop: send the conversation to the model, run the tool it asks
for, add the result, repeat until it answers. `prompts.py` holds what the agent is told, and `state.py` what a
run returns. The loop knows nothing about refunds; that is all in `tools/`.
