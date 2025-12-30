## Node Interface Contract

All conversation nodes must:
- Accept `state: CallState`
- Return a partial state update (`dict`)
- Never modify graph routing
- Never return the full state

Nodes may:
- Append assistant messages to `state["messages"]`
- Update verification, payment, and outcome fields
- Use LLM helpers from `src/utils/llm.py`

Routing logic is owned exclusively by `graph.py`.
