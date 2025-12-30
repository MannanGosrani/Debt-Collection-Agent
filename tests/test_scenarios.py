# tests/test_scenarios.py

from src.state import create_initial_state
from src.graph import app

def run(phone, user_msgs):
    state = create_initial_state(phone)
    state = app.invoke(state)

    for msg in user_msgs:
        state["messages"].append({"role": "user", "content": msg})
        state["last_user_input"] = msg
        state = app.invoke(state)
        if state.get("is_complete"):
            break
    return state


def test_already_paid():
    result = run("+919876543210", [
        "Yes",
        "15-03-1985",
        "I already paid last week"
    ])
    assert result["payment_status"] == "paid"
    assert result["is_complete"] is True


def test_dispute():
    result = run("+919876543211", [
        "Yes",
        "22-07-1990",
        "This loan is not mine"
    ])
    assert result["payment_status"] == "disputed"
    assert result["is_complete"] is True


def test_unable_to_pay():
    result = run("+919876543212", [
        "Yes",
        "05-11-1988",
        "I cannot pay right now"
    ])
    assert result["payment_status"] == "unable"
    assert len(result["offered_plans"]) > 0
