# =======================================================================
# Import required modules from the Firebase Admin SDK.
# -----------------------------------------------------------------------
import firebase_admin
from firebase_admin import credentials, firestore

# =======================================================================
# Step 1: Initialize Firebase Admin SDK
# -----------------------------------------------------------------------
# Load the service account key JSON file.
# Replace "firebase_service_key.json" with the path to your Firebase service account JSON.
cred = credentials.Certificate("firebase_service_key.json")

# Initialize the Firebase Admin SDK with the service account credentials.
firebase_admin.initialize_app(cred)

# =======================================================================
# Step 2: Get Firestore client
# -----------------------------------------------------------------------
# Create a Firestore client to interact with the Firestore database.
db = firestore.client()

# =======================================================================
# Function: add_user
# Purpose: Adds a new user document to the "users" collection in Firestore.
# -----------------------------------------------------------------------
def add_user(fname, sname, email, business_phone):
    try:
        # Step 3: Reference the 'users' collection.
        # A new document reference is created with an auto-generated unique ID.
        doc_ref = db.collection("users").document()

        # Step 4: Define the user data to be stored in Firestore.
        # 'connections' is initialized as an empty list.
        user_data = {
            "fname": fname,
            "sname": sname,
            "email": email,
            "business_phone": business_phone,
            "connections": [],  # Empty list for connections, to be populated later.
        }

        # Step 5: Add the user document to Firestore with the defined data.
        doc_ref.set(user_data)

        # Print a success message with the auto-generated document ID.
        print(f"User {fname} {sname} added successfully with ID: {doc_ref.id}")

    except Exception as e:
        # In case of an error, print the error message.
        print(f"An error occurred: {e}")

# =======================================================================
# Example usage: Create and add users to Firestore.
# -----------------------------------------------------------------------
add_user(
    fname="John",
    sname="O'Malley",
    email="john.omalley@example.com",
    business_phone="+1234567890"
)

# Add another user to demonstrate adding multiple entries.
add_user(
    fname="Jane",
    sname="Doe",
    email="jane.doe@example.com",
    business_phone="+9876543210"
)
