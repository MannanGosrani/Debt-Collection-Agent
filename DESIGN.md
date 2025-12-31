# Design Document – Debt Collection Agent

## 1. System Overview

This project implements a **deterministic, state-driven debt collection voice agent** using **LangGraph**.
The agent conducts structured conversations for debt recovery, including identity verification, disclosure, payment intent handling, negotiation, and call closure.

The system is **self-contained**, with mock customer and loan data, and does not rely on external CRMs or services.

Core goals:

- Enforce correct conversation sequencing
- Handle multiple real-world debt collection scenarios
- Ensure deterministic, debuggable behavior
- Validate correctness using LangSmith evaluations

## 2. Graph Design (LangGraph)

The conversation flow is modeled as a **finite state machine** using LangGraph.

### Nodes

Each node represents a single conversational responsibility:

- **Greeting Node**
  Initiates the call and confirms the customer’s identity at a high level.

- **Verification Node**
  Performs DOB-based authentication with:

  - Maximum 3 attempts
  - Multiple DOB format support
  - Early termination on failure

- **Disclosure Node**
  Provides the legally required disclosure and outstanding amount details.
  Ensures disclosure is performed **only once** using state flags.

- **Payment Check Node**
  Classifies customer intent into:

  - paid
  - disputed
  - callback
  - willing
  - unable

- **Negotiation Node**
  Offers payment options such as EMI, partial payment, or deferred payment when applicable.

- **Closing Node**
  Records call outcome, updates final state, and terminates the conversation cleanly.

### Routing

Routing is fully **state-based**, using:

- `awaiting_user`
- `is_verified`
- `payment_status`
- `is_complete`

This ensures:

- No infinite loops
- No duplicate prompts
- Clean termination paths

## 3. State Management

A single shared `CallState` object flows through the graph.

Key state categories:

- Conversation control: `messages`, `stage`, `awaiting_user`
- Verification: `verification_attempts`, `is_verified`
- Payment handling: `payment_status`, `ptp_amount`, `ptp_date`
- Outcome tracking: `call_outcome`, `call_summary`, `is_complete`

This approach guarantees:

- Deterministic execution
- Easy debugging
- Clear traceability in LangSmith

## 4. LLM Prompting and Intent Classification

To keep the system deterministic and self-contained, **rule-based intent classification** is used as the primary mechanism.

Intent priority is explicitly enforced:

1. paid
2. disputed
3. callback
4. unable
5. willing

This ordering avoids common misclassification issues (e.g., callback requests being treated as payment intent).

The system is designed so that an external LLM can be enabled later without changing graph logic.

## 5. LangSmith Evaluation Strategy

LangSmith is used for:

- Tracing each conversation run
- Dataset-based evaluation
- Regression detection

### Dataset

Six required scenarios are covered:

- Happy Path (PTP)
- Already Paid
- Dispute
- Negotiation
- Callback Request
- Verification Failed

### Evaluators

Custom evaluators validate:

- `is_verified`
- `call_outcome`
- `payment_status`

All scenarios pass with a full score after final fixes.

LangSmith traces were critical in debugging:

- Intent misclassification
- Verification termination logic
- State propagation issues

## 6. Key Challenges and Resolutions

### Callback Misclassification

**Issue:**
Callback requests were incorrectly classified as payment intent.

**Resolution:**
Reordered intent classification logic so callback detection precedes payment checks.

### Verification Flow Termination

**Issue:**
Verification retries could loop indefinitely without clean termination.

**Resolution:**
Introduced strict attempt counting and explicit `is_complete` termination.

### State Propagation Bugs

**Issue:**
Some node transitions did not correctly update shared state.

**Resolution:**
Standardized node return contracts and enforced consistent state updates.

## 7. Final Outcome

The system achieves:

- Fully deterministic conversational behavior
- Clear separation of responsibilities
- Complete LangSmith evaluation coverage
- Production-style robustness suitable for real-world extension
