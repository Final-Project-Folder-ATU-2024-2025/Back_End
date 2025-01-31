import firebase_admin
from firebase_admin import credentials, firestore

# Step 1: Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase_service_key.json")  # Replace with your JSON file path
firebase_admin.initialize_app(cred)

# Step 2: Get Firestore client
db = firestore.client()

# Function to add a user to Firestore
def add_user(fname, sname, email, business_phone):
    try:
        # Step 3: Reference the 'users' collection
        doc_ref = db.collection("users").document()  # Automatically generate a unique ID

        # Step 4: User data to store
        user_data = {
            "fname": fname,
            "sname": sname,
            "email": email,
            "business_phone": business_phone,
            "connections": [],  # Empty list for connections, to be populated later
        }

        # Step 5: Add the document to Firestore
        doc_ref.set(user_data)

        print(f"User {fname} {sname} added successfully with ID: {doc_ref.id}")

    except Exception as e:
        print(f"An error occurred: {e}")


# Example usage: Create and add a user
add_user(
    fname="John",
    sname="O'Malley",
    email="john.omalley@example.com",
    business_phone="+1234567890"
)

# Add more users if needed
add_user(
    fname="Jane",
    sname="Doe",
    email="jane.doe@example.com",
    business_phone="+9876543210"
)
