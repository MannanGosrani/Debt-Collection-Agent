from dotenv import load_dotenv
load_dotenv() 

from langsmith.evaluation import evaluate
from src.state import create_initial_state
from src.graph import app


def run_agent(inputs: dict) -> dict:
    state = create_initial_state(inputs["phone"])
    state = app.invoke(state)

    for msg in inputs["user_messages"]:
        state["messages"].append({"role": "user", "content": msg})
        state["last_user_input"] = msg
        state = app.invoke(state)

    return state


def check_verified(run, example) -> dict:
    expected = example.outputs.get("is_verified")
    actual = run.outputs.get("is_verified")
    return {
        "score": 1 if expected == actual else 0,
        "key": "verified_correct"
    }


if __name__ == "__main__":
    results = evaluate(
        run_agent,
        data="debt-collection-eval",
        evaluators=[check_verified],
        experiment_prefix="v1"
    )

    print("LangSmith evaluation complete")
    print(results)
