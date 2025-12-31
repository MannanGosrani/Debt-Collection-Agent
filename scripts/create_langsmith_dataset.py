# scripts/create_langsmith_dataset.py

from dotenv import load_dotenv
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv(dotenv_path=".env")

from langsmith import Client

client = Client()

# Delete old dataset
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
    description="Debt collection agent evaluation"
)

print(f"✅ Created new dataset: {dataset.name}")
print(f"Dataset ID: {dataset.id}\n")

test_cases = [
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
            "call_outcome": "willing",
            "payment_status": "willing"
        }
    },
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
            "call_outcome": "paid",
            "payment_status": "paid"
        }
    },
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
            "call_outcome": "disputed",
            "payment_status": "disputed"
        }
    },
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
            "call_outcome": "unable",
            "payment_status": "unable"
        }
    },
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
            "payment_status": None
        }
    },
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
            "call_outcome": "callback",
            "payment_status": "callback"
        }
    }
]

for i, tc in enumerate(test_cases, 1):
    client.create_example(
        inputs=tc["input"],
        outputs=tc["expected"],
        dataset_id=dataset.id
    )
    print(f"✅ Case {i}: {tc['input']['scenario']}")

print(f"\n{'='*60}")
print(f"✅ Dataset created with {len(test_cases)} test cases")
print(f"{'='*60}")