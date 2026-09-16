import os
import requests


# Supply test credentials through the environment; never store credentials here.
KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    raise RuntimeError("Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET before running this test.")


url = "https://api.razorpay.com/v1/orders"


payment_order = {
    "amount": 10000,       # ₹100.00 because amount is in paise
    "currency": "INR",
    "receipt": "college_exam_001",
    "notes": {
        "student_id": "STUDENT001",
        "purpose": "Examination Fee"
    }
}


response = requests.post(
    url,
    auth=(KEY_ID, KEY_SECRET),
    json=payment_order
)


print("HTTP Status:", response.status_code)
print("Response:")

try:
    print(response.json())
except Exception:
    print(response.text)
