# Debt Collection Agent (LangGraph + LangSmith)

An AI-powered Debt Collection Voice Agent built using LangGraph for conversational orchestration and LangSmith for observability and evaluation.

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

## Project Structure

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

### Mannan Gosrani (Owner / Integrator)
- Overall system architecture and orchestration
- LangGraph state machine and flow integration
- Git workflow, branching strategy, and conflict resolution
- LangSmith setup (tracing, datasets, evaluations)
- Deterministic LLM fallback logic
- CLI-based manual testing (main.py)
- Fixed evaluation script state propagation issues
- Debugged and resolved verification flow bugs
- Final integration, testing, and documentation

### Atharva Ghuge
- Identity verification flow implementation
- Verification node with DOB-based authentication
- Verification failure and retry logic (max 3 attempts)
- Added awaiting_user flags for proper flow control
- Implemented robust DOB matching with multiple format support

### Shruti
- Payment intent classification using LLM
- Negotiation flow (EMI, partial, deferred payments)
- Call closing logic and outcome recording
- Dispute and already-paid flow handling
- Payment status tracking and PTP recording

## Setup Instructions

### 1. Clone the Repository
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

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Note**: pytest is not required to run this project.

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

**Never commit .env to GitHub**

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

All agent runs are automatically logged to LangSmith, including:
- Node-level execution
- Latency metrics
- Token usage
- Errors and exceptions

### View Results
- **Evaluation Dataset**: [View all 6 test scenarios and results](https://smith.langchain.com/o/c2bf1b47-4401-464a-8074-2a60bb18ef20/datasets)

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
- LangSmith → Datasets → debt-collection-eval

## Test Scenarios Coverage

All 6 scenarios passing in LangSmith evaluation:

1. **Happy Path PTP** - Customer commits to payment on a specific date
   - Expected: `is_verified: true`, `payment_status: willing`, `call_outcome: willing`

2. **Already Paid** - Customer claims payment was already made
   - Expected: `is_verified: true`, `payment_status: paid`, `call_outcome: paid`

3. **Dispute** - Customer disputes the debt validity
   - Expected: `is_verified: true`, `payment_status: disputed`, `call_outcome: disputed`

4. **Negotiate Accept** - Customer negotiates and accepts a payment plan
   - Expected: `is_verified: true`, `payment_status: unable`, `negotiation_offered: true`

5. **Verification Failed** - Customer fails identity verification after 3 attempts
   - Expected: `is_verified: false`, `call_outcome: verification_failed`, `no_disclosure: true`

6. **Callback Request** - Customer requests a callback
   - Expected: `is_verified: true`, `payment_status: callback`, `call_outcome: callback`

View detailed results: [LangSmith Dataset](https://smith.langchain.com/o/c2bf1b47-4401-464a-8074-2a60bb18ef20/datasets)

## Evaluation Logic

Custom evaluators implemented:

- **verified_correct**: Checks if agent verification outcome matches expected result
- **payment_status_correct**: Validates payment status classification
- **call_outcome_correct**: Verifies final call outcome
- **check_scenario_outcomes**: Scenario-specific validation (PTP recorded, dispute recorded, etc.)

Experiments are versioned automatically (v3-required-cases-*) for comparison.

## Key Features

- Secure DOB-based identity verification (max 3 attempts)
- Natural language intent classification using LLM
- Flexible negotiation with multiple payment plans
- Complete LangSmith tracing and evaluation
- Proper state management with awaiting_user flags
- Robust error handling and graceful failures
- 100% test scenario pass rate

## Design Decisions

- **LangGraph** chosen for explicit state transitions and auditability
- **LangSmith** used for real-world observability (not mock logging)
- **Deterministic fallback** added to prevent LLM failures blocking execution
- **No external databases** — fully self-contained as per assignment scope
- **Awaiting_user flags** implemented for proper conversation flow control
- **State propagation** carefully managed in evaluation scripts to ensure accurate testing

## Challenges Faced & Solutions

### 1. State Management in Evaluation
**Problem**: User inputs were not being propagated correctly to the graph, resulting in empty `last_user_input` during verification.

**Solution**: Refactored the `provide_input_and_continue` helper to create a new state dict instead of mutating in place, ensuring all state updates are properly passed to graph invocations.

### 2. Verification Flow Control
**Problem**: The graph was not waiting for user input at critical points, causing verification to run with empty responses.

**Solution**: Added `awaiting_user` flags to all nodes that require user input (greeting, verification, disclosure), allowing the evaluation script to properly pause and resume execution.

### 3. DOB Matching Reliability
**Problem**: Date of birth verification was failing due to format variations (e.g., "15-03-1985" vs "15/03/1985").

**Solution**: Implemented robust DOB matching with normalization, supporting multiple separators (-, /, space) and both exact and substring matching.

### 4. Merge Conflicts During Integration
**Problem**: Multiple team members working on the same files caused merge conflicts.

**Solution**: Established feature-branch workflow and used `git checkout --ours` strategy to resolve conflicts by keeping the most recent working versions.
