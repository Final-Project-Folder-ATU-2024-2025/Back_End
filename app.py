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
CORS(app)  # Enable Cross-Origin Resource Sharing (CORS) for all routes

# ---------------------------
# 2. Initialize Firebase Admin SDK
# ---------------------------
# Path to the service account JSON file
service_account_path = "firebase_service_key.json"

try:
    # Load the service account key from the JSON file
    cred = credentials.Certificate(service_account_path)
    
    # Initialize the Firebase Admin SDK with the credentials
    firebase_admin.initialize_app(cred)
    
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    # Stop execution and log an error if initialization fails
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
    
    Steps:
      1. Validate input.
      2. Check if a user with the given email already exists.
      3. Create a new user in Firebase Authentication.
      4. Store the user data in Firestore under the "users" collection.
         The document ID is set to the Firebase user UID, and an empty
         'connections' array is added to hold future contact UIDs.
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
        
        # Validate that all required fields are provided
        if not (first_name and surname and telephone and email and password):
            return jsonify({"error": "All fields are required"}), 400
        
        # Check if a user with the provided email already exists
        try:
            existing_user = auth.get_user_by_email(email)
            return jsonify({"error": "User already exists", "uid": existing_user.uid}), 400
        except firebase_admin.auth.UserNotFoundError:
            pass  # No existing user, proceed to create one
        
        # Create a new user in Firebase Authentication
        user = auth.create_user(
            email=email,
            password=password,
            display_name=f"{first_name} {surname}"
        )
        
        # Store the new user's data in Firestore
        db.collection("users").document(user.uid).set({
            "firstName": first_name,
            "surname": surname,
            "telephone": telephone,
            "email": email,
            "uid": user.uid,
            "connections": []  # Empty array for future contacts
        })
        
        # Return a success message with the new user's UID
        return jsonify({"message": "User created successfully!", "userId": user.uid}), 201
    
    except Exception as e:
        # Log and return any errors that occur during the process
        print(f"🔥 ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5. Define the Login Endpoint
# ---------------------------
@app.route('/api/login', methods=['POST'])
def login():
    """
    This login endpoint accepts a JSON payload with:
      - email (string)
      - password (string)
      
    For demonstration purposes, we assume the credentials are valid.
    This endpoint queries Firestore for a user document matching the provided email,
    and if found, returns a dummy token along with the user's firstName and surname.
    """
    try:
        # Retrieve JSON data from the request
        data = request.get_json()
        print("Login endpoint received data:", data)
        
        # Ensure both email and password are provided
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password are required'}), 400
        
        email = data['email']
        
        # Query Firestore for the user document matching the provided email
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).limit(1).stream()
        user_doc = None
        for doc in query:
            user_doc = doc
            break

        if user_doc is None:
            return jsonify({"error": "User not found"}), 404

        user_data = user_doc.to_dict()

        # Return a dummy token along with firstName and surname.
        return jsonify({
            "message": "Logged in successfully!",
            "token": "dummy-token",  # In production, generate a real token.
            "firstName": user_data.get("firstName", ""),
            "surname": user_data.get("surname", "")
        }), 200

    except Exception as e:
        print(f"🔥 ERROR in login: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 6. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
