# Debt Collection Agent (LangGraph + LangSmith)

An AI-powered **Debt Collection Voice Agent** built using **LangGraph** for conversational orchestration and **LangSmith** for observability and evaluation.

This agent simulates real-world debt collection calls by:

- Verifying customer identity
- Explaining outstanding dues
- Handling different customer responses (paid, disputed, unable, willing, callback)
- Negotiating payment options
- Closing calls professionally
- Tracking performance using LangSmith

## Architecture Overview

### Core Layers

- **Agent Orchestration**: LangGraph state machine
- **LLM Layer**: Google Gemini (with deterministic fallback)
- **Observability & Evaluation**: LangSmith
- **CLI Interface**: Manual call simulation via terminal

### Project Structure

```
debt-collection-agent/
├── experiments/
│   └── langsmith_eval.py                   # LangSmith evaluation script
├── scripts/
│   └── create_langsmith_dataset.py         # Dataset creation for LangSmith
├── src/
│   ├── nodes/                              # Conversation flow nodes
│   │   ├── __init__.py
│   │   ├── closing.py                      # Call closing & outcome recording
│   │   ├── disclosure.py                   # Legal disclosure node
│   │   ├── greeting.py                     # Initial greeting node
│   │   ├── negotiation.py                  # Payment negotiation logic
│   │   ├── payment_check.py                # Payment intent classification
│   │   └── verification.py                 # Identity verification
│   ├── utils/
│   │   ├── __init__.py
│   │   └── llm.py                          # LLM + deterministic fallback
│   ├── __init__.py
│   ├── data.py                             # In-memory customer & call records
│   ├── graph.py                            # LangGraph flow definition
│   └── state.py                            # Shared call state
├── tests/
│   └── test_scenarios.py                   # Test scenarios
├── .gitignore                              # Git ignore rules
├── .env.example                            # Environment variables template
├── main.py                                 # CLI for manual testing
├── README.md                               # Project documentation
└── requirements.txt                        # Python dependencies
```

## Team Contributions

### **Mannan Gosrani (Owner / Integrator)**

- Overall system architecture and orchestration
- LangGraph state machine and flow integration
- Git workflow, branching strategy, and conflict resolution
- LangSmith setup (tracing, datasets, evaluations)
- Deterministic LLM fallback logic
- CLI-based manual testing (`main.py`)
- Final integration, testing, and documentation

### **Atharva**

- Identity verification flow
- Verification node implementation
- Verification failure and retry logic

### **Shruti**

- Payment intent classification
- Negotiation flow (EMI, partial, deferred payments)
- Call closing logic and outcome recording

## ⚙️ Setup Instructions

### 1️. Clone the Repository

```bash
git clone https://github.com/MannanGosrani/Debt-Collection-Agent.git
cd Debt-Collection-Agent
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
```

### 3️. Install Dependencies

```bash
pip install -r requirements.txt
```

> `pytest` is **not required** to run this project.

## Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_gemini_api_key

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=debt-collection-agent

LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=debt-collection-agent
```

> **Never commit `.env` to GitHub**

## Running the Agent (Manual CLI)

Start an interactive test call:

```bash
python main.py
```

Example:

```
=== Debt Collection Agent Test ===
Available test customers:
1. +919876543210 (Rajesh Kumar)
2. +919876543211 (Priya Sharma)
3. +919876543212 (Amit Patel)
```

You can then simulate a real conversation step-by-step.

## LangSmith Observability & Evaluation

### Tracing

All agent runs are automatically logged to **LangSmith**, including:

- Node-level execution
- Latency
- Errors
- Token usage

### Create Evaluation Dataset

```bash
python scripts/create_langsmith_dataset.py
```

### Run Evaluation

```bash
python -m experiments.langsmith_eval
```

This evaluates:

- Verification correctness
- Agent behavior across predefined test scenarios

Results are viewable in:

```
LangSmith → Datasets → debt-collection-eval
```

## Evaluation Logic

Custom evaluator example:

- `verified_correct`: checks if agent verification outcome matches expected result

Experiments are versioned automatically (`v1-*`) for comparison.

## Design Decisions

- **LangGraph** chosen for explicit state transitions and auditability
- **LangSmith** used for real-world observability (not mock logging)
- **Deterministic fallback** added to prevent LLM failures blocking execution
- No external databases — fully self-contained as per assignment scope

## Current Status

- ✅ All core flows implemented
- ✅ Team contributions merged
- ✅ LangSmith evaluation integrated
- ✅ Manual CLI testing functional
- ✅ Ready for review / submission
