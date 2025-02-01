# app.py

import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------------------
# 1. Create the Flask App
# ---------------------------
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing (CORS)

# ---------------------------
# 2. Initialize Firebase Admin SDK
# ---------------------------

# Path to the service account JSON file
service_account_path = "firebase_service_key.json"

try:
    # Load the service account key
    cred = credentials.Certificate(service_account_path)
    
    # Initialize the Firebase Admin SDK with the credentials
    firebase_admin.initialize_app(cred)
    
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    # If initialization fails, stop execution and print an error
    raise ValueError(f"🔥 ERROR: Failed to initialize Firebase Admin SDK. {str(e)}")

# ---------------------------
# 3. Create a Firestore Client
# ---------------------------
# This client allows you to interact with your Firestore database.
db = firestore.client()

# ---------------------------
# 4. Define the API Endpoint to Create a User
# ---------------------------
@app.route('/api/create-user', methods=['POST'])
def create_user():
    """
    This endpoint creates a new user. It expects a JSON payload with:
    - firstName (string)
    - surname (string)
    - telephone (string)
    - email (string)
    - password (string)
    
    It performs the following steps:
    1. Validates the input.
    2. Checks if a user with the given email already exists.
    3. Creates a new user in Firebase Authentication.
    4. Stores the user data in Firestore under the "users" collection.
       The document ID in Firestore is set to the Firebase user UID.
       A 'connections' field is also added as an empty array to hold future contact UIDs.
    """
    try:
        # Retrieve JSON data from the request
        data = request.get_json()
        
        # Extract user details from the payload
        first_name = data.get("firstName")
        surname = data.get("surname")
        telephone = data.get("telephone")
        email = data.get("email")
        password = data.get("password")
        
        # ---------------------------
        # 4.1. Validate the Input
        # ---------------------------
        if not (first_name and surname and telephone and email and password):
            return jsonify({"error": "All fields are required"}), 400
        
        # ---------------------------
        # 4.2. Check if the User Already Exists
        # ---------------------------
        try:
            # Try to retrieve a user with the provided email from Firebase Authentication
            existing_user = auth.get_user_by_email(email)
            return jsonify({"error": "User already exists", "uid": existing_user.uid}), 400
        except firebase_admin.auth.UserNotFoundError:
            # If the user is not found, we proceed to create a new one
            pass
        
        # ---------------------------
        # 4.3. Create a New User in Firebase Authentication
        # ---------------------------
        user = auth.create_user(
            email=email,
            password=password,
            display_name=f"{first_name} {surname}"
        )
        
        # ---------------------------
        # 4.4. Store the User Data in Firestore
        # ---------------------------
        # Here, we add the user to the "users" collection.
        # The document ID is the same as the Firebase Authentication UID.
        # We also add an empty array for 'connections' which can later hold UIDs of contacts/friends.
        db.collection("users").document(user.uid).set({
            "firstName": first_name,
            "surname": surname,
            "telephone": telephone,
            "email": email,
            "uid": user.uid,
            "connections": []  # This array will store UIDs of other users (e.g., contacts)
        })
        
        # Return a success message with the new user's UID
        return jsonify({"message": "User created successfully!", "userId": user.uid}), 201
    
    except Exception as e:
        # Log and return any errors that occur during the process
        print(f"🔥 ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
