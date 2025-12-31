# scripts/create_langsmith_dataset.py

from dotenv import load_dotenv
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv(dotenv_path=".env")

from langsmith import Client

client = Client()

# Delete old dataset if exists
try:
    datasets = list(client.list_datasets(dataset_name="debt-collection-eval"))
    for ds in datasets:
        client.delete_dataset(dataset_id=ds.id)
        print(f"✅ Deleted old dataset: {ds.name}")
except Exception as e:
    print(f"No existing dataset to delete: {e}")

# Create fresh dataset
dataset = client.create_dataset(
    "debt-collection-eval",
    description="Required test scenarios for debt collection agent - 6 cases"
)

print(f"✅ Created new dataset: {dataset.name}")
print(f"Dataset ID: {dataset.id}\n")

# Define the 6 required test cases
test_cases = [
    # Case 1: Happy Path PTP
    {
        "input": {
            "phone": "+919876543210",
            "scenario": "Happy Path PTP",
            "user_responses": {
                "greeting": "Yes",
                "verification": "15-03-1985",
                "disclosure": "I want to pay on 5th January"
            }
        },
        "expected": {
            "is_verified": True,
            "payment_status": "willing",
            "call_outcome": "willing",
            "ptp_recorded": True
        }
    },
    
    # Case 2: Already Paid
    {
        "input": {
            "phone": "+919876543211",
            "scenario": "Already Paid",
            "user_responses": {
                "greeting": "Yes",
                "verification": "22-07-1990",
                "disclosure": "I already paid last week"
            }
        },
        "expected": {
            "is_verified": True,
            "payment_status": "paid",
            "call_outcome": "paid",
            "closed_confirmed": True
        }
    },
    
    # Case 3: Dispute
    {
        "input": {
            "phone": "+919876543212",
            "scenario": "Dispute",
            "user_responses": {
                "greeting": "Yes",
                "verification": "05-11-1988",
                "disclosure": "This is wrong, I never took this loan"
            }
        },
        "expected": {
            "is_verified": True,
            "payment_status": "disputed",
            "call_outcome": "disputed",
            "dispute_recorded": True
        }
    },
    
    # Case 4: Negotiate → Accept (3 month plan)
    {
        "input": {
            "phone": "+919876543210",
            "scenario": "Negotiate Accept",
            "user_responses": {
                "greeting": "Yes",
                "verification": "15-03-1985",
                "disclosure": "I can't pay full amount",
                "negotiation": "I can do 3 month plan"
            }
        },
        "expected": {
            "is_verified": True,
            "payment_status": "unable",
            "call_outcome": "unable",
            "negotiation_offered": True,
            "ptp_with_plan": True
        }
    },
    
    # Case 5: Verification Failed
    {
        "input": {
            "phone": "+919876543210",
            "scenario": "Verification Failed",
            "user_responses": {
                "greeting": "Yes",
                "verification_attempts": ["wrong-dob-1", "wrong-dob-2", "wrong-dob-3"]
            }
        },
        "expected": {
            "is_verified": False,
            "call_outcome": "verification_failed",
            "is_complete": True,
            "no_disclosure": True
        }
    },
    
    # Case 6: Callback Request
    {
        "input": {
            "phone": "+919876543211",
            "scenario": "Callback Request",
            "user_responses": {
                "greeting": "Yes",
                "verification": "22-07-1990",
                "disclosure": "Call me next week"
            }
        },
        "expected": {
            "is_verified": True,
            "payment_status": "callback",
            "call_outcome": "callback",
            "callback_noted": True
        }
    }
]

# Add test cases to dataset
for i, tc in enumerate(test_cases, 1):
    client.create_example(
        inputs=tc["input"],
        outputs=tc["expected"],
        dataset_id=dataset.id
    )
    print(f"✅ Case {i}: {tc['input']['scenario']}")

print(f"\n{'='*60}")
print(f"✅ Dataset created successfully with {len(test_cases)} test cases")
print(f"{'='*60}")
print(f"\nView at: https://smith.langchain.com")