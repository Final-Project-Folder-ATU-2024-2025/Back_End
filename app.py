from flask import Flask, request, jsonify
from flask_cors import CORS
import pyrebase

# Firebase configuration
firebase_config = {
    "apiKey": "AIzaSyBFcz4pxHeTejDbw4nMZT8vR28DYkkb2kw",
    "authDomain": "collabfy-dc20d.firebaseapp.com",
    "databaseURL": "https://collabfy-dc20d-default-rtdb.europe-west1.firebasedatabase.app",
    "projectId": "collabfy-dc20d",
    "storageBucket": "collabfy-dc20d.appspot.com",
    "messagingSenderId": "146475704216",
    "appId": "1:146475704216:web:de8856edb4798a7db215ed",
}

# Initialize Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Route to create a new user
@app.route('/api/create-user', methods=['POST'])
def create_user():
    try:
        # Get user details from the request
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        # Validate input
        if not name or not email or not password:
            return jsonify({"error": "All fields are required"}), 400

        # Create user in Firebase Authentication
        user = auth.create_user_with_email_and_password(email, password)
        user_id = user['localId']

        # Store additional user information in Firebase Realtime Database
        db.child("users").child(user_id).set({
            "name": name,
            "email": email
        })

        return jsonify({"message": "User created successfully", "userId": user_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route to retrieve all users (for testing purposes)
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        # Fetch all users from the database
        users = db.child("users").get()
        users_dict = users.val()

        # If no users exist, return an empty list
        if not users_dict:
            return jsonify([]), 200

        # Convert Firebase dictionary to a list
        user_list = [{"id": key, **value} for key, value in users_dict.items()]
        return jsonify(user_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
