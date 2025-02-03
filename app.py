import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# ---------------------------
# 1. Create the Flask App
# ---------------------------
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ---------------------------
# 2. Initialize Firebase Admin SDK
# ---------------------------
service_account_path = "firebase_service_key.json"
try:
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    raise ValueError(f"🔥 ERROR: Failed to initialize Firebase Admin SDK. {str(e)}")

# ---------------------------
# 3. Create a Firestore Client
# ---------------------------
db = firestore.client()

# ---------------------------
# 4. Define the API Endpoint to Create a User
# ---------------------------
@app.route('/api/create-user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        first_name = data.get("firstName")
        surname = data.get("surname")
        telephone = data.get("telephone")
        email = data.get("email")
        password = data.get("password")
        
        if not (first_name and surname and telephone and email and password):
            return jsonify({"error": "All fields are required"}), 400
        
        try:
            existing_user = auth.get_user_by_email(email)
            return jsonify({"error": "User already exists", "uid": existing_user.uid}), 400
        except firebase_admin.auth.UserNotFoundError:
            pass
        
        user = auth.create_user(
            email=email,
            password=password,
            display_name=f"{first_name} {surname}"
        )
        
        db.collection("users").document(user.uid).set({
            "firstName": first_name,
            "surname": surname,
            "telephone": telephone,
            "email": email,
            "uid": user.uid,
            "connections": []
        })
        
        return jsonify({"message": "User created successfully!", "userId": user.uid}), 201
    
    except Exception as e:
        print(f"🔥 ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5. Define the Login Endpoint
# ---------------------------
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        print("Login endpoint received data:", data)
        
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password are required'}), 400
        
        email = data['email']
        
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).limit(1).stream()
        user_doc = None
        for doc in query:
            user_doc = doc
            break

        if user_doc is None:
            return jsonify({"error": "User not found"}), 404

        user_data = user_doc.to_dict()

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
# 6. Define the Search Users Endpoint
# ---------------------------
@app.route('/api/search-users', methods=['POST', 'OPTIONS'])
@cross_origin()  # Ensure CORS headers are sent, including for the preflight OPTIONS request.
def search_users():
    """
    This endpoint accepts a JSON payload with:
      - query (string)
    If the query contains an '@', it searches for an exact email match.
    Otherwise, it retrieves all users and filters by firstName or surname containing the query.
    Returns a list of matching user profiles.
    """
    try:
        data = request.get_json()
        search_query = data.get("query", "").strip()
        if not search_query:
            return jsonify({"error": "Query is required"}), 400

        users_ref = db.collection("users")
        results = []
        if "@" in search_query:
            q = users_ref.where("email", "==", search_query).stream()
            for doc in q:
                results.append(doc.to_dict())
        else:
            all_docs = users_ref.stream()
            for doc in all_docs:
                user = doc.to_dict()
                if (search_query.lower() in user.get("firstName", "").lower() or 
                    search_query.lower() in user.get("surname", "").lower()):
                    results.append(user)
        
        return jsonify({"results": results}), 200

    except Exception as e:
        print(f"🔥 ERROR in search-users: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 7. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
