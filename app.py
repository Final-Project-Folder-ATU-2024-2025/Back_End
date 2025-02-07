import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from datetime import datetime

# ---------------------------
# 1. Create the Flask App
# ---------------------------
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
# 4. Create User Endpoint
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
        
        # Create the user document in the "users" collection.
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
# 5. Login Endpoint
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
# 6. Search Users Endpoint
# ---------------------------
@app.route('/api/search-users', methods=['POST', 'OPTIONS'])
@cross_origin()
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
# 7. Send Connection Request Endpoint
# ---------------------------
@app.route('/api/send-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
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
        
        # Create a notification in the recipient’s notifications subcollection.
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
# 8. Cancel Connection Request Endpoint
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
# 9. Respond to Connection Request Endpoint
# ---------------------------
@app.route('/api/respond-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
def respond_connection_request():
    try:
        data = request.get_json()
        request_id = data.get("requestId")
        action = data.get("action")  # Must be "accepted" or "rejected"
        if not request_id or action not in ["accepted", "rejected"]:
            return jsonify({"error": "requestId and a valid action (accepted or rejected) are required"}), 400
        
        req_doc_ref = db.collection("connectionRequests").document(request_id)
        req_doc = req_doc_ref.get()
        if not req_doc.exists:
            return jsonify({"error": "Connection request not found"}), 404
        
        req_data = req_doc.to_dict()
        from_user = req_data.get("fromUserId")
        to_user = req_data.get("toUserId")
        
        # Update the connection request status.
        req_doc_ref.update({"status": action})
        
        # Delete the original notification from the recipient’s notifications subcollection.
        notif_query = db.collection("users").document(to_user).collection("notifications") \
                        .where("connectionRequestId", "==", request_id).stream()
        for notif in notif_query:
            db.collection("users").document(to_user).collection("notifications").document(notif.id).delete()
        
        # If accepted, add each user to the other’s connections array.
        if action == "accepted":
            users_ref = db.collection("users")
            from_doc = users_ref.document(from_user).get()
            to_doc = users_ref.document(to_user).get()
            if from_doc.exists and to_doc.exists:
                from_data = from_doc.to_dict()
                to_data = to_doc.to_dict()
                connection_info_for_from = {
                    "uid": to_user,
                    "firstName": to_data.get("firstName", ""),
                    "surname": to_data.get("surname", ""),
                    "email": to_data.get("email", ""),
                    "telephone": to_data.get("telephone", "")
                }
                connection_info_for_to = {
                    "uid": from_user,
                    "firstName": from_data.get("firstName", ""),
                    "surname": from_data.get("surname", ""),
                    "email": from_data.get("email", ""),
                    "telephone": from_data.get("telephone", "")
                }
                from_connections = from_data.get("connections", [])
                to_connections = to_data.get("connections", [])
                if not any(conn.get("uid") == to_user for conn in from_connections):
                    from_connections.append(connection_info_for_from)
                    users_ref.document(from_user).update({"connections": from_connections})
                if not any(conn.get("uid") == from_user for conn in to_connections):
                    to_connections.append(connection_info_for_to)
                    users_ref.document(to_user).update({"connections": to_connections})
        
        # Create a response notification for the requester.
        response_notification_data = {
            "type": "response",
            "message": f"Your connection request has been {action}.",
            "fromUser": {},
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
# 10. User Connections Endpoint
# ---------------------------
@app.route('/api/user-connections', methods=['POST', 'OPTIONS'])
@cross_origin()
def user_connections():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            return jsonify({"error": "User not found"}), 404
        user_data = user_doc.to_dict()
        connections = user_data.get("connections", [])
        return jsonify({"connections": connections}), 200
    except Exception as e:
        print(f"🔥 ERROR in user_connections: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 11. Notifications Endpoint
# ---------------------------
@app.route('/api/notifications', methods=['POST', 'OPTIONS'])
@cross_origin()
def notifications():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        notifs_ref = db.collection("users").document(user_id).collection("notifications")
        query = notifs_ref.stream()

        notifications = []
        for doc in query:
            ndata = doc.to_dict()
            ndata["id"] = doc.id
            notifications.append(ndata)
        notifications.sort(key=lambda n: n.get("timestamp", 0), reverse=True)
        return jsonify({"notifications": notifications}), 200

    except Exception as e:
        print(f"🔥 ERROR in notifications: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 12. Dismiss Notification Endpoint
# ---------------------------
@app.route('/api/dismiss-notification', methods=['POST', 'OPTIONS'])
@cross_origin()
def dismiss_notification():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        notification_id = data.get("notificationId")
        if not user_id or not notification_id:
            return jsonify({"error": "userId and notificationId are required"}), 400

        notif_ref = db.collection("users").document(user_id).collection("notifications").document(notification_id)
        notif_ref.delete()
        return jsonify({"message": "Notification dismissed"}), 200

    except Exception as e:
        print(f"🔥 ERROR in dismiss_notification: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 13. Disconnect Endpoint
# ---------------------------
@app.route('/api/disconnect', methods=['POST', 'OPTIONS'])
@cross_origin()
def disconnect():
    try:
        data = request.get_json()
        user_id = data.get("userId")  # Current user's id
        disconnect_user_id = data.get("disconnectUserId")  # The user to disconnect from
        if not user_id or not disconnect_user_id:
            return jsonify({"error": "userId and disconnectUserId are required"}), 400

        users_ref = db.collection("users")
        user_doc = users_ref.document(user_id).get()
        disconnect_doc = users_ref.document(disconnect_user_id).get()
        if not user_doc.exists or not disconnect_doc.exists:
            return jsonify({"error": "One or both users not found"}), 404

        user_data = user_doc.to_dict()
        disconnect_data = disconnect_doc.to_dict()

        # Remove disconnect_user_id from current user's connections
        user_connections = user_data.get("connections", [])
        updated_user_connections = [conn for conn in user_connections if conn.get("uid") != disconnect_user_id]
        users_ref.document(user_id).update({"connections": updated_user_connections})

        # Remove current user id from disconnect user's connections
        disconnect_connections = disconnect_data.get("connections", [])
        updated_disconnect_connections = [conn for conn in disconnect_connections if conn.get("uid") != user_id]
        users_ref.document(disconnect_user_id).update({"connections": updated_disconnect_connections})

        return jsonify({"message": "Disconnected successfully"}), 200

    except Exception as e:
        print(f"🔥 ERROR in disconnect: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 14. CREATE PROJECT Endpoint
# ---------------------------
@app.route('/api/create-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def create_project():
    try:
        data = request.get_json()
        # Extract the required fields from the request JSON
        project_name = data.get("projectName")
        description = data.get("description")
        tasks = data.get("tasks")  # Expected to be a list of objects { taskName, taskDescription }
        deadline_str = data.get("deadline")  # Expected in YYYY-MM-DD format
        owner_id = data.get("ownerId")  # The UID of the user creating the project

        if not (project_name and description and owner_id and deadline_str):
            return jsonify({"error": "Project name, description, deadline, and ownerId are required"}), 400

        # If tasks are not provided, use an empty list
        if tasks is None:
            tasks = []

        # Convert the deadline string to a datetime object
        try:
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Deadline must be in YYYY-MM-DD format"}), 400

        # Create the project document in the "projects" collection
        project_data = {
            "projectName": project_name,
            "description": description,
            "tasks": tasks,
            "deadline": deadline_date,
            "ownerId": owner_id,
            "createdAt": firestore.SERVER_TIMESTAMP
        }
        project_ref = db.collection("projects").document()
        project_ref.set(project_data)

        return jsonify({"message": "Project created successfully!", "projectId": project_ref.id}), 201

    except Exception as e:
        print(f"🔥 ERROR in create_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 15. Run the Flask App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
