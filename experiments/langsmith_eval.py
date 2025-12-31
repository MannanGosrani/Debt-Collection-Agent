# experiments/langsmith_eval.py

from dotenv import load_dotenv
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv()

from langsmith.evaluation import evaluate
from src.state import create_initial_state
from src.graph import app


def run_agent(inputs: dict) -> dict:
    """
    Run agent through complete conversation flow.
    """
    phone = inputs["phone"]
    scenario = inputs["scenario"]
    user_responses = inputs["user_responses"]
    
    # Initialize state
    state = create_initial_state(phone)
    if not state:
        return {
            "is_verified": None,
            "call_outcome": None,
            "payment_status": None,
            "error": "Customer not found"
        }

    try:
        # Use invoke instead of stream for cleaner state management
        config = {"recursion_limit": 25}
        
        # Step 1: Greeting
        state = app.invoke(state, config)
        
        # Step 2: Respond to greeting
        if "greeting" in user_responses and state.get("awaiting_user"):
            state["messages"].append({
                "role": "user",
                "content": user_responses["greeting"]
            })
            state["last_user_input"] = user_responses["greeting"]
            state["awaiting_user"] = False
            state = app.invoke(state, config)
        
        # Step 3: Handle verification
        if "verification_attempts" in user_responses:
            # Multiple verification attempts (failed verification scenario)
            for attempt in user_responses["verification_attempts"]:
                if state.get("is_complete"):
                    break
                if state.get("awaiting_user"):
                    state["messages"].append({
                        "role": "user",
                        "content": attempt
                    })
                    state["last_user_input"] = attempt
                    state["awaiting_user"] = False
                    state = app.invoke(state, config)
        
        elif "verification" in user_responses:
            # Single verification attempt (successful)
            if state.get("awaiting_user") and not state.get("is_complete"):
                state["messages"].append({
                    "role": "user",
                    "content": user_responses["verification"]
                })
                state["last_user_input"] = user_responses["verification"]
                state["awaiting_user"] = False
                state = app.invoke(state, config)
        
        # Step 4: Handle disclosure response
        if "disclosure" in user_responses and not state.get("is_complete"):
            if state.get("awaiting_user"):
                state["messages"].append({
                    "role": "user",
                    "content": user_responses["disclosure"]
                })
                state["last_user_input"] = user_responses["disclosure"]
                state["awaiting_user"] = False
                state = app.invoke(state, config)
        
        # Step 5: Handle negotiation response (if applicable)
        if "negotiation" in user_responses and not state.get("is_complete"):
            if state.get("awaiting_user"):
                state["messages"].append({
                    "role": "user",
                    "content": user_responses["negotiation"]
                })
                state["last_user_input"] = user_responses["negotiation"]
                state["awaiting_user"] = False
                state = app.invoke(state, config)
        
        # Return final state outputs
        return {
            "is_verified": state.get("is_verified"),
            "call_outcome": state.get("call_outcome"),
            "payment_status": state.get("payment_status"),
            "final_stage": state.get("stage"),
            "is_complete": state.get("is_complete")
        }

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR in {scenario}: {e}")
        print(error_trace)
        return {
            "is_verified": None,
            "call_outcome": None,
            "payment_status": None,
            "error": str(e),
            "traceback": error_trace
        }


def check_verified(run, example):
    """Check if verification status matches expected."""
    expected = example.outputs.get("is_verified")
    actual = run.outputs.get("is_verified")
    
    passed = expected == actual
    
    return {
        "score": 1 if passed else 0,
        "key": "is_verified"
    }


def check_call_outcome(run, example):
    """Check if call outcome matches expected."""
    expected = example.outputs.get("call_outcome")
    actual = run.outputs.get("call_outcome")
    
    passed = expected == actual
    
    return {
        "score": 1 if passed else 0,
        "key": "call_outcome"
    }


def check_payment_status(run, example):
    """Check if payment status matches expected."""
    expected = example.outputs.get("payment_status")
    actual = run.outputs.get("payment_status")
    
    # Handle None cases
    if expected is None:
        passed = actual is None
    else:
        passed = expected == actual
    
    return {
        "score": 1 if passed else 0,
        "key": "payment_status"
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Starting LangSmith Evaluation")
    print("Testing 6 Required Scenarios")
    print("=" * 60)
    
    results = evaluate(
        run_agent,
        data="debt-collection-eval",
        evaluators=[
            check_verified,
            check_call_outcome,
            check_payment_status
        ],
        experiment_prefix="v4-fixed-invoke",
        max_concurrency=1
    )

    print("\n" + "=" * 60)
    print("✅ Evaluation Complete!")
    print("=" * 60)
    print("\nView detailed results at the URL above ☝️")