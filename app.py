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

# After-request handler to add CORS headers to every response
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

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
            "token": "dummy-token",  # Replace with a real token in production.
            "firstName": user_data.get("firstName", ""),
            "surname": user_data.get("surname", ""),
            "uid": user_data.get("uid", "")
        }), 200

    except Exception as e:
        print(f"🔥 ERROR in login: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 6. Define the Search Users Endpoint
# ---------------------------
@app.route('/api/search-users', methods=['POST', 'OPTIONS'])
@cross_origin()  # Allow CORS for this endpoint
def search_users():
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
# 7. Define the Send Connection Request Endpoint
# ---------------------------
@app.route('/api/send-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()  # Ensure CORS for preflight and actual requests
def send_connection_request():
    try:
        data = request.get_json()
        from_user = data.get("fromUserId")
        to_user = data.get("toUserId")
        if not from_user or not to_user:
            return jsonify({"error": "Both fromUserId and toUserId are required"}), 400

        # Create connection request document
        req_ref = db.collection("connectionRequests").document()
        req_data = {
            "fromUserId": from_user,
            "toUserId": to_user,
            "status": "pending"  # pending, accepted, or rejected
        }
        req_ref.set(req_data)
        
        # Create a notification for the recipient
        notification_data = {
            "type": "request",
            "message": "The following user wants to Connect:",
            "fromUser": {},
            "toUserId": to_user,
            "status": "unread",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        sender_doc = db.collection("users").document(from_user).get()
        if sender_doc.exists:
            sender_data = sender_doc.to_dict()
            notification_data["fromUser"] = {
                "firstName": sender_data.get("firstName", ""),
                "surname": sender_data.get("surname", ""),
                "email": sender_data.get("email", ""),
                "telephone": sender_data.get("telephone", "")
            }
        notif_ref = db.collection("notifications").document()
        notif_ref.set(notification_data)
        
        return jsonify({"message": "Connection request sent", "requestId": req_ref.id}), 200
    except Exception as e:
        print(f"🔥 ERROR in send-connection-request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 8. Define the Cancel Connection Request Endpoint
# ---------------------------
@app.route('/api/cancel-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
def cancel_connection_request():
    try:
        data = request.get_json()
        from_user = data.get("fromUserId")
        to_user = data.get("toUserId")
        if not from_user or not to_user:
            return jsonify({"error": "Both fromUserId and toUserId are required"}), 400

        requests_ref = db.collection("connectionRequests")
        query = requests_ref.where("fromUserId", "==", from_user) \
                            .where("toUserId", "==", to_user) \
                            .where("status", "==", "pending").stream()
        deleted = False
        for doc in query:
            requests_ref.document(doc.id).delete()
            deleted = True

        if deleted:
            return jsonify({"message": "Connection request cancelled"}), 200
        else:
            return jsonify({"error": "No pending request found"}), 404

    except Exception as e:
        print(f"🔥 ERROR in cancel-connection-request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 9. Define the Notifications Endpoint
# ---------------------------
@app.route('/api/notifications', methods=['POST', 'OPTIONS'])
@cross_origin()
def notifications():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        notifs_ref = db.collection("notifications")
        # Retrieve notifications without using order_by to avoid requiring a composite index.
        query = notifs_ref.where("toUserId", "==", user_id).stream()

        notifications = []
        for doc in query:
            ndata = doc.to_dict()
            ndata["id"] = doc.id
            notifications.append(ndata)
        # Manually sort notifications by "timestamp" (if available) in descending order.
        notifications.sort(key=lambda n: n.get("timestamp", 0), reverse=True)
        return jsonify({"notifications": notifications}), 200

    except Exception as e:
        print(f"🔥 ERROR in notifications: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 10. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
