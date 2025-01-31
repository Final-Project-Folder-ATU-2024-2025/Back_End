import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS

# Load Firebase Admin SDK from JSON file
try:
    cred = credentials.Certificate("firebase_service_key.json")
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    raise ValueError(f"🔥 ERROR: Failed to initialize Firebase Admin SDK. {str(e)}")

# Firestore Database
db = firestore.client()

# API Route: Create User
@app.route('/api/create-user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        first_name = data.get('firstName')
        surname = data.get('surname')
        telephone = data.get('telephone')
        email = data.get('email')
        password = data.get('password')

        # Validate input
        if not first_name or not surname or not email or not password or not telephone:
            return jsonify({"error": "All fields are required"}), 400

        # Create Firebase Authentication User
        user = auth.create_user(
            email=email,
            password=password,
            display_name=f"{first_name} {surname}"
        )

        # Store User in Firestore
        db.collection("users").document(user.uid).set({
            "firstName": first_name,
            "surname": surname,
            "telephone": telephone,
            "email": email,
            "uid": user.uid
        })

        return jsonify({"message": "User created successfully!", "userId": user.uid}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
