# experiments/langsmith_eval.py

from dotenv import load_dotenv
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv()

from langsmith.evaluation import evaluate
from src.state import create_initial_state
from src.graph import app


# -------------------------
# Helper: step graph until it asks user or finishes
# -------------------------
def step_until_awaiting(state):
    while not state.get("awaiting_user") and not state.get("is_complete"):
        state = app.invoke(state, config={"recursion_limit": 25})
    return state


# -------------------------
# Helper: provide user input and continue
# -------------------------
def provide_input_and_continue(state, user_input):
    """Add user input to state and step until next wait point"""
    # CRITICAL: Create a complete new state dict with the user input
    updated_state = dict(state)  # Copy current state
    updated_state["messages"] = state["messages"] + [{
        "role": "user",
        "content": user_input
    }]
    updated_state["last_user_input"] = user_input
    updated_state["awaiting_user"] = False
    
    # Now invoke the graph with the updated state
    return step_until_awaiting(updated_state)


# -------------------------
# Main runner
# -------------------------
def run_agent(inputs: dict) -> dict:
    phone = inputs["phone"]
    user_responses = inputs["user_responses"]

    state = create_initial_state(phone)
    if not state:
        return {"error": "Customer not found"}

    stages_completed = []

    try:
        # -------------------------
        # Greeting
        # -------------------------
        state = step_until_awaiting(state)
        stages_completed.append("greeting")

        if "greeting" in user_responses:
            state = provide_input_and_continue(state, user_responses["greeting"])

        # -------------------------
        # Verification
        # -------------------------
        if "verification_attempts" in user_responses:
            # Verification failure path
            for attempt in user_responses["verification_attempts"]:
                if state.get("is_complete"):
                    break
                state = provide_input_and_continue(state, attempt)
                stages_completed.append("verification_attempt")

        elif "verification" in user_responses:
            state = provide_input_and_continue(state, user_responses["verification"])
            stages_completed.append("verification")

        # -------------------------
        # Disclosure
        # -------------------------
        if "disclosure" in user_responses and not state.get("is_complete"):
            state = provide_input_and_continue(state, user_responses["disclosure"])
            stages_completed.append("disclosure")

        # -------------------------
        # Negotiation (optional)
        # -------------------------
        if "negotiation" in user_responses and not state.get("is_complete"):
            state = provide_input_and_continue(state, user_responses["negotiation"])
            stages_completed.append("negotiation")

        # -------------------------
        # Final Output
        # -------------------------
        return {
            "is_verified": state.get("is_verified"),
            "payment_status": state.get("payment_status"),
            "call_outcome": state.get("call_outcome"),
            "is_complete": state.get("is_complete"),
            "final_stage": state.get("stage"),
            "message_count": len(state.get("messages", [])),
            "stages_completed": stages_completed,

            # Scenario helpers
            "ptp_recorded": state.get("payment_status") in ["willing", "unable"],
            "dispute_recorded": state.get("payment_status") == "disputed",
            "callback_noted": state.get("payment_status") == "callback",
            "closed_confirmed": state.get("payment_status") == "paid",
            "no_disclosure": not state.get("has_disclosed", False),
        }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "stages_completed": stages_completed
        }


# -------------------------
# Evaluators (unchanged)
# -------------------------
def check_verified(run, example):
    return {
        "score": 1 if run.outputs.get("is_verified") == example.outputs.get("is_verified") else 0,
        "key": "verified_correct"
    }


def check_payment_status(run, example):
    expected = example.outputs.get("payment_status")
    if expected is None:
        return {"score": None, "key": "payment_status_correct"}

    return {
        "score": 1 if run.outputs.get("payment_status") == expected else 0,
        "key": "payment_status_correct"
    }


def check_call_outcome(run, example):
    expected = example.outputs.get("call_outcome")
    if expected is None:
        return {"score": None, "key": "call_outcome_correct"}

    return {
        "score": 1 if run.outputs.get("call_outcome") == expected else 0,
        "key": "call_outcome_correct"
    }


def check_scenario_outcomes(run, example):
    scenario = example.inputs.get("scenario", "")

    if "Happy Path" in scenario:
        return {
            "score": int(run.outputs.get("ptp_recorded") == example.outputs.get("ptp_recorded")),
            "key": "ptp_recorded"
        }

    if "Already Paid" in scenario:
        return {
            "score": int(run.outputs.get("closed_confirmed") == example.outputs.get("closed_confirmed")),
            "key": "closed_confirmed"
        }

    if "Dispute" in scenario:
        return {
            "score": int(run.outputs.get("dispute_recorded") == example.outputs.get("dispute_recorded")),
            "key": "dispute_recorded"
        }

    if "Verification Failed" in scenario:
        return {
            "score": int(run.outputs.get("no_disclosure") == example.outputs.get("no_disclosure")),
            "key": "no_disclosure"
        }

    if "Callback" in scenario:
        return {
            "score": int(run.outputs.get("callback_noted") == example.outputs.get("callback_noted")),
            "key": "callback_noted"
        }

    return {"score": None, "key": "scenario_check"}


if __name__ == "__main__":
    results = evaluate(
        run_agent,
        data="debt-collection-eval",
        evaluators=[
            check_verified,
            check_payment_status,
            check_call_outcome,
            check_scenario_outcomes
        ],
        experiment_prefix="v3-required-cases",
        max_concurrency=1
    )

    print("✅ LangSmith evaluation complete")