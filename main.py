# main.py

from src.state import create_initial_state
from src.graph import app


def main():
    print("=== Debt Collection Agent Test ===")
    print("Available test customers:")
    print("  1. +919876543210 (Rajesh Kumar, DOB: 15-03-1985)")
    print("  2. +919876543211 (Priya Sharma, DOB: 22-07-1990)")
    print("  3. +919876543212 (Amit Patel, DOB: 05-11-1988)")
    print()

    phone = input("Enter phone number: ").strip()
    state = create_initial_state(phone)

    if not state:
        print("Customer not found!")
        return

    print("\n--- Starting Call ---\n")

    # Conversation loop
    while not state.get("is_complete"):
        try:
            # Invoke the graph
            state = app.invoke(state, config={"recursion_limit": 25})
            
            # Print the last agent message if it exists
            if state.get("messages") and state["messages"][-1]["role"] == "assistant":
                print(f"Agent: {state['messages'][-1]['content']}\n")
            
            # Check if call is complete
            if state.get("is_complete"):
                break
            
            # If the agent is waiting for user input, get it
            if state.get("awaiting_user"):
                user_input = input("You: ").strip()
                
                # Allow empty input but warn user
                if user_input == "":
                    print("(Please provide a response)\n")
                    continue
                
                if user_input.lower() in ["quit", "exit"]:
                    print("\nCall ended by user.")
                    break
                
                # Add user message to state
                state["messages"].append({
                    "role": "user",
                    "content": user_input
                })
                state["last_user_input"] = user_input
                state["awaiting_user"] = False
            else:
                # If not awaiting and not complete, something went wrong
                print("\nUnexpected state - ending call")
                break
                
        except Exception as e:
            print(f"\nError during call: {e}")
            import traceback
            traceback.print_exc()
            break

    print("\n=== Call Summary ===")
    print(f"Outcome: {state.get('call_outcome', 'unknown')}")
    print(f"Verified: {state.get('is_verified')}")
    if state.get("call_summary"):
        print(f"\n{state['call_summary']}")


if __name__ == "__main__":
    main()