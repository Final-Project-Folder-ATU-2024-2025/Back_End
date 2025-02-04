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
        
        # Create user document in "users" collection.
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

        # Create a connection request document.
        req_ref = db.collection("connectionRequests").document()
        req_data = {
            "fromUserId": from_user,
            "toUserId": to_user,
            "status": "pending"
        }
        req_ref.set(req_data)
        
        # Create a notification in the recipient’s (to_user’s) notifications subcollection.
        notification_data = {
            "type": "request",
            "message": "The following user wants to Connect:",
            "fromUser": {},
            "status": "unread",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "connectionRequestId": req_ref.id
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
        notif_ref = db.collection("users").document(to_user).collection("notifications").document()
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
            # Also delete the corresponding notification from the recipient’s notifications subcollection.
            notif_query = db.collection("users").document(to_user).collection("notifications") \
                            .where("connectionRequestId", "==", doc.id).stream()
            for notif_doc in notif_query:
                db.collection("users").document(to_user).collection("notifications").document(notif_doc.id).delete()
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
# 9. Define an Endpoint for Responding to a Connection Request
# (This handles acceptance or rejection, updates the request status, deletes the original notification, and notifies the requester.)
# ---------------------------
@app.route('/api/respond-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
def respond_connection_request():
    try:
        data = request.get_json()
        request_id = data.get("requestId")
        action = data.get("action")  # should be "accepted" or "rejected"
        if not request_id or action not in ["accepted", "rejected"]:
            return jsonify({"error": "requestId and a valid action (accepted or rejected) are required"}), 400
        
        # Retrieve the connection request document.
        req_doc_ref = db.collection("connectionRequests").document(request_id)
        req_doc = req_doc_ref.get()
        if not req_doc.exists:
            return jsonify({"error": "Connection request not found"}), 404
        
        req_data = req_doc.to_dict()
        from_user = req_data.get("fromUserId")
        to_user = req_data.get("toUserId")
        
        # Update the request status.
        req_doc_ref.update({"status": action})
        
        # Delete the notification from the recipient’s notifications subcollection.
        notif_query = db.collection("users").document(to_user).collection("notifications") \
                        .where("connectionRequestId", "==", request_id).stream()
        for notif in notif_query:
            db.collection("users").document(to_user).collection("notifications").document(notif.id).delete()
        
        # Create a new notification for the requester informing them of the response.
        response_notification_data = {
            "type": "response",
            "message": f"Your connection request has been {action}.",
            "fromUser": {},  # details of the user who responded (i.e. to_user)
            "status": "unread",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        target_doc = db.collection("users").document(to_user).get()
        if target_doc.exists:
            target_data = target_doc.to_dict()
            response_notification_data["fromUser"] = {
                "firstName": target_data.get("firstName", ""),
                "surname": target_data.get("surname", ""),
                "email": target_data.get("email", ""),
                "telephone": target_data.get("telephone", "")
            }
        resp_notif_ref = db.collection("users").document(from_user).collection("notifications").document()
        resp_notif_ref.set(response_notification_data)
        
        return jsonify({"message": f"Connection request {action}"}), 200
    except Exception as e:
        print(f"🔥 ERROR in respond_connection_request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 10. Define the Notifications Endpoint
# ---------------------------
@app.route('/api/notifications', methods=['POST', 'OPTIONS'])
@cross_origin()
def notifications():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        # Retrieve notifications from the user's "notifications" subcollection.
        notifs_ref = db.collection("users").document(user_id).collection("notifications")
        query = notifs_ref.stream()

        notifications = []
        for doc in query:
            ndata = doc.to_dict()
            ndata["id"] = doc.id
            notifications.append(ndata)
        # Manually sort notifications by timestamp (if present) in descending order.
        notifications.sort(key=lambda n: n.get("timestamp", 0), reverse=True)
        return jsonify({"notifications": notifications}), 200

    except Exception as e:
        print(f"🔥 ERROR in notifications: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 11. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
