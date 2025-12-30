from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from langsmith import Client

client = Client()

dataset = client.create_dataset(
    "debt-collection-eval",
    description="Test scenarios for debt collection agent"
)

test_cases = [
    {
        "input": {
            "phone": "+919876543210",
            "user_messages": ["Yes", "15-03-1985", "I can pay"]
        },
        "expected": {
            "is_verified": True,
            "payment_status": "willing"
        }
    },
    {
        "input": {
            "phone": "+919876543210",
            "user_messages": ["Yes", "wrong-dob", "wrong", "wrong"]
        },
        "expected": {
            "is_verified": False,
            "call_outcome": "verification_failed"
        }
    }
]

for tc in test_cases:
    client.create_example(
        inputs=tc["input"],
        outputs=tc["expected"],
        dataset_id=dataset.id
    )

print("✅ Dataset created successfully")
