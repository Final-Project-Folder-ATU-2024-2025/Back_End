import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin.firestore import ArrayUnion  # Used for updating arrays in Firestore documents
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from datetime import datetime
import bcrypt  # For hashing and verifying passwords

# ---------------------------
# 1. Create the Flask App
# ---------------------------
# This section creates the Flask application and enables CORS (Cross-Origin Resource Sharing)
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.after_request
def after_request(response):
    # This function adds necessary headers to allow cross-origin requests.
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ---------------------------
# 2. Initialize Firebase Admin SDK
# ---------------------------
# This section initializes the Firebase Admin SDK using a service account key.
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
# This section creates a client for Firestore, which will be used for all database interactions.
db = firestore.client()

# ---------------------------
# 4. Create User Endpoint
# ---------------------------
# This endpoint creates a new user. It validates the required fields, hashes the password,
# creates a Firebase Authentication user, and stores additional user details in Firestore.
@app.route('/api/create-user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        print("Received create-user data:", data)
        first_name = data.get("firstName")
        surname = data.get("surname")
        telephone = data.get("telephone", "")
        email = data.get("email").lower()
        password = data.get("password")
        if not (first_name and surname and email and password):
            return jsonify({"error": "First name, surname, email, and password are required"}), 400
        # Validate password with regex (minimum 10 characters, at least one number and special character)
        import re
        password_pattern = re.compile(r'^(?=.*\d)(?=.*[@$!%*?&]).{10,}$')
        if not password_pattern.match(password):
            return jsonify({"error": "Password must be at least 10 characters long and include at least one number and one special character."}), 400
        try:
            # Check if user already exists by email
            auth.get_user_by_email(email)
            return jsonify({"error": "User already exists"}), 400
        except firebase_admin.auth.UserNotFoundError:
            pass
        # Hash the password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # Create a new Firebase Authentication user
        user = auth.create_user(email=email, password=password, display_name=f"{first_name} {surname}")
        # Save additional user details in Firestore
        db.collection("users").document(user.uid).set({
            "firstName": first_name,
            "surname": surname,
            "telephone": telephone,
            "email": email,
            "uid": user.uid,
            "connections": [],
            "password_hash": hashed_password
        })
        return jsonify({"message": "User created successfully!", "userId": user.uid}), 201
    except Exception as e:
        print(f"🔥 ERROR in create_user: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5. Login Endpoint – Token Verification
# ---------------------------
# This endpoint verifies an ID token from the client using Firebase Admin SDK and returns
# additional user details stored in Firestore.
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'idToken' not in data:
            return jsonify({'error': 'ID token is required'}), 400
        id_token = data['idToken']
        # Verify the token
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token.get('uid')
        # Retrieve user data from Firestore
        user_doc = db.collection("users").document(uid).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        return jsonify({
            "message": "Logged in successfully!",
            "uid": uid,
            "firstName": user_data.get("firstName", ""),
            "surname": user_data.get("surname", ""),
            "email": user_data.get("email", "")
        }), 200
    except Exception as e:
        print(f"🔥 ERROR in login: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5A. Update User Settings Endpoint
# ---------------------------
# This endpoint updates non-password user settings (currently telephone).
@app.route('/api/update-user-settings', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_user_settings():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        new_telephone = data.get("telephone")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        update_data = {}
        if new_telephone:
            update_data["telephone"] = new_telephone
        if not update_data:
            return jsonify({"error": "No data provided to update"}), 400
        db.collection("users").document(user_id).update(update_data)
        return jsonify({"message": "User settings updated successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in update_user_settings: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5B. Update User Password Endpoint
# ---------------------------
# This endpoint updates the user's password after validating the new password.
@app.route('/api/update-user-password', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_user_password():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        new_password = data.get("newPassword")
        if not user_id or not new_password:
            return jsonify({"error": "userId and newPassword are required"}), 400
        import re
        password_pattern = re.compile(r'^(?=.*\d)(?=.*[@$!%*?&]).{10,}$')
        if not password_pattern.match(new_password):
            return jsonify({"error": "New password must be at least 10 characters long and include at least one number and one special character."}), 400
        # Update the password in Firebase Authentication
        auth.update_user(user_id, password=new_password)
        # Hash the new password and update it in Firestore
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.collection("users").document(user_id).set({"password_hash": new_hashed_password}, merge=True)
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in update_user_password: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 5C. Update User Endpoint (Combined Settings Update)
# ---------------------------
# This endpoint updates multiple user properties (name, telephone, password) in one request.
@app.route('/api/update-user', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_user():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        new_telephone = data.get("telephone")
        new_password = data.get("newPassword")
        new_first_name = data.get("firstName")
        new_surname = data.get("surname")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        update_data = {}
        if new_first_name:
            update_data["firstName"] = new_first_name
        if new_surname:
            update_data["surname"] = new_surname
        if new_telephone:
            update_data["telephone"] = new_telephone
        if new_password:
            auth.update_user(user_id, password=new_password)
            new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_data["password_hash"] = new_hashed_password
        if update_data:
            db.collection("users").document(user_id).update(update_data)
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in update_user: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 6. Search Users Endpoint
# ---------------------------
# This endpoint allows searching for users by email, first name, or surname.
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
            search_query = search_query.lower()
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
        print(f"🔥 ERROR in search_users: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 7. Send Connection Request Endpoint
# ---------------------------
# This endpoint creates a new connection request and sends a notification to the recipient.
@app.route('/api/send-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
def send_connection_request():
    try:
        data = request.get_json()
        from_user = data.get("fromUserId")
        to_user = data.get("toUserId")
        if not from_user or not to_user:
            return jsonify({"error": "Both fromUserId and toUserId are required"}), 400
        req_ref = db.collection("connectionRequests").document()
        req_data = {
            "fromUserId": from_user,
            "toUserId": to_user,
            "status": "pending"
        }
        req_ref.set(req_data)
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
        print(f"🔥 ERROR in send_connection_request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 8. Cancel Connection Request Endpoint
# ---------------------------
# This endpoint cancels a pending connection request and removes its notification.
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
        print(f"🔥 ERROR in cancel_connection_request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 9. Respond to Connection Request Endpoint
# ---------------------------
# This endpoint processes a connection request response (accepted or rejected) and updates
# the user connections accordingly, also sending appropriate notifications.
@app.route('/api/respond-connection-request', methods=['POST', 'OPTIONS'])
@cross_origin()
def respond_connection_request():
    try:
        data = request.get_json()
        request_id = data.get("requestId")
        action = data.get("action")  # "accepted" or "rejected"
        if not request_id or action not in ["accepted", "rejected"]:
            return jsonify({"error": "requestId and a valid action (accepted or rejected) are required"}), 400
        req_doc_ref = db.collection("connectionRequests").document(request_id)
        req_doc = req_doc_ref.get()
        if not req_doc.exists:
            return jsonify({"error": "Connection request not found"}), 404
        req_data = req_doc.to_dict()
        from_user = req_data.get("fromUserId")
        to_user = req_data.get("toUserId")
        req_doc_ref.update({"status": action})
        notif_query = db.collection("users").document(to_user).collection("notifications") \
                        .where("connectionRequestId", "==", request_id).stream()
        for notif in notif_query:
            db.collection("users").document(to_user).collection("notifications").document(notif.id).delete()
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
# This endpoint returns the list of connections for a given user.
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
# This endpoint returns notifications for a user. An optional exclude_type parameter can be provided.
@app.route('/api/notifications', methods=['POST', 'OPTIONS'])
@cross_origin()
def notifications():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        exclude_type = data.get("excludeType")  # Optionally exclude notifications of a given type
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        notifs_ref = db.collection("users").document(user_id).collection("notifications")
        query = notifs_ref.stream()
        notifications = []
        for doc in query:
            ndata = doc.to_dict()
            if exclude_type and ndata.get("type") == exclude_type:
                continue
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
# This endpoint allows a user to dismiss (delete) a notification.
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
# This endpoint disconnects two users by removing them from each other's connection lists.
@app.route('/api/disconnect', methods=['POST', 'OPTIONS'])
@cross_origin()
def disconnect():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        disconnect_user_id = data.get("disconnectUserId")
        if not user_id or not disconnect_user_id:
            return jsonify({"error": "userId and disconnectUserId are required"}), 400
        users_ref = db.collection("users")
        user_doc = users_ref.document(user_id).get()
        disconnect_doc = users_ref.document(disconnect_user_id).get()
        if not user_doc.exists or not disconnect_doc.exists:
            return jsonify({"error": "One or both users not found"}), 404
        user_data = user_doc.to_dict()
        disconnect_data = disconnect_doc.to_dict()
        user_connections = user_data.get("connections", [])
        updated_user_connections = [conn for conn in user_connections if conn.get("uid") != disconnect_user_id]
        users_ref.document(user_id).update({"connections": updated_user_connections})
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
# This endpoint creates a new project with specified details including tasks, deadline, and owner.
@app.route('/api/create-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def create_project():
    try:
        data = request.get_json()
        project_name = data.get("projectName")
        description = data.get("description")
        tasks = data.get("tasks")
        deadline_str = data.get("deadline")
        owner_id = data.get("ownerId")
        if not (project_name and description and owner_id and deadline_str):
            return jsonify({"error": "Project name, description, deadline, and ownerId are required"}), 400
        if tasks is None:
            tasks = []
        try:
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Deadline must be in YYYY-MM-DD format"}), 400
        project_data = {
            "projectName": project_name,
            "description": description,
            "tasks": tasks,
            "deadline": deadline_date,
            "ownerId": owner_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "team": [],
            "teamIds": []
        }
        project_ref = db.collection("projects").document()
        project_ref.set(project_data)
        return jsonify({"message": "Project created successfully!", "projectId": project_ref.id}), 201
    except Exception as e:
        print(f"🔥 ERROR in create_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 14B. UPDATE PROJECT Endpoint (Status Notification)
# ---------------------------
# This endpoint updates a project's details and, if the status changes, sends notifications to collaborators.
@app.route('/api/update-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_project():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        project_name = data.get("projectName")
        description = data.get("description")
        tasks = data.get("tasks")
        deadline_str = data.get("deadline")
        status = data.get("status")  # New status update (e.g., "In Progress", "Complete")
        requester_id = data.get("requesterId")  # UID of the user making the update
        
        if not project_id:
            return jsonify({"error": "Project ID is required"}), 400
        
        project_ref = db.collection("projects").document(project_id)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        
        current_project_data = project_doc.to_dict()
        update_data = {}
        if project_name:
            update_data["projectName"] = project_name
        if description:
            update_data["description"] = description
        if tasks is not None:
            update_data["tasks"] = tasks
        if deadline_str:
            try:
                deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
                update_data["deadline"] = deadline_date
            except ValueError:
                return jsonify({"error": "Deadline must be in YYYY-MM-DD format"}), 400
        if status:
            update_data["status"] = status
        
        if update_data:
            project_ref.update(update_data)
            if status and requester_id:
                updated_project_doc = project_ref.get()
                updated_project_data = updated_project_doc.to_dict()
                requester_doc = db.collection("users").document(requester_id).get()
                if requester_doc.exists:
                    requester_data = requester_doc.to_dict()
                    requester_name = f"{requester_data.get('firstName', '')} {requester_data.get('surname', '')}".strip()
                else:
                    requester_name = "A user"
                recipients = set(updated_project_data.get("teamIds", []))
                owner_id = updated_project_data.get("ownerId")
                if owner_id and owner_id != requester_id:
                    recipients.add(owner_id)
                recipients.discard(requester_id)
                notification_message = f"{requester_name} changed project {updated_project_data.get('projectName', 'Unknown')} status to {status}."
                for uid in recipients:
                    notif_data = {
                        "type": "status-update",
                        "message": notification_message,
                        "status": "unread",
                        "timestamp": firestore.SERVER_TIMESTAMP,
                        "projectId": project_id,
                        "projectName": updated_project_data.get("projectName", "Unknown"),
                        "changedBy": requester_name,
                        "newStatus": status
                    }
                    db.collection("users").document(uid).collection("notifications").document().set(notif_data)
            return jsonify({"message": "Project updated successfully"}), 200
        else:
            return jsonify({"message": "Nothing to update"}), 200
    except Exception as e:
        print(f"🔥 ERROR in update_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 15. My Projects Endpoint
# ---------------------------
# This endpoint retrieves projects that the user owns or is a team member of.
@app.route('/api/my-projects', methods=['POST', 'OPTIONS'])
@cross_origin()
def my_projects():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        projects_ref = db.collection("projects")
        owner_query = projects_ref.where("ownerId", "==", user_id).stream()
        team_query = projects_ref.where("teamIds", "array_contains", user_id).stream()
        projects = []
        seen = set()
        for doc in owner_query:
            proj = doc.to_dict()
            proj["projectId"] = doc.id
            projects.append(proj)
            seen.add(doc.id)
        for doc in team_query:
            if doc.id not in seen:
                proj = doc.to_dict()
                proj["projectId"] = doc.id
                projects.append(proj)
                seen.add(doc.id)
        return jsonify({"projects": projects}), 200
    except Exception as e:
        print(f"🔥 ERROR in my_projects: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 15B. Get Project Endpoint
# ---------------------------
# This endpoint retrieves detailed information for a specific project.
@app.route('/api/get-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def get_project():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        if not project_id:
            return jsonify({"error": "projectId is required"}), 400
        project_doc = db.collection("projects").document(project_id).get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        project_data["projectId"] = project_doc.id
        return jsonify({"project": project_data}), 200
    except Exception as e:
        print(f"🔥 ERROR in get_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 16. Project Deadlines Endpoint
# ---------------------------
# This endpoint retrieves deadlines for projects owned by a user.
@app.route('/api/project-deadlines', methods=['POST', 'OPTIONS'])
@cross_origin()
def project_deadlines():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        if not user_id:
            return jsonify({"error": "userId is required"}), 400
        projects_ref = db.collection("projects")
        query = projects_ref.where("ownerId", "==", user_id).stream()
        deadlines = []
        for doc in query:
            proj = doc.to_dict()
            deadlines.append({
                "projectId": doc.id,
                "projectName": proj.get("projectName", ""),
                "deadline": proj.get("deadline", None)
            })
        return jsonify({"deadlines": deadlines}), 200
    except Exception as e:
        print(f"🔥 ERROR in project_deadlines: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 17. Respond to Project Invitation Endpoint
# ---------------------------
# This endpoint allows a user to accept or decline a project invitation.
@app.route('/api/respond-project-invitation', methods=['POST', 'OPTIONS'])
@cross_origin()
def respond_project_invitation():
    try:
        data = request.get_json()
        invitationId = data.get("invitationId")
        action = data.get("action")  # Expected values: "accepted" or "declined"
        userId = data.get("userId")
        if not (invitationId and action and userId):
            return jsonify({"error": "Missing fields"}), 400
        if action not in ["accepted", "declined"]:
            return jsonify({"error": "Invalid action"}), 400
        notif_ref = db.collection("users").document(userId).collection("notifications").document(invitationId)
        notif_doc = notif_ref.get()
        if not notif_doc.exists:
            return jsonify({"error": "Invitation not found"}), 404
        notif_data = notif_doc.to_dict()
        projectId = notif_data.get("projectId")
        projectName = notif_data.get("projectName")
        ownerId = notif_data.get("ownerId", "")
        notif_ref.delete()
        if action == "accepted":
            project_ref = db.collection("projects").document(projectId)
            accepted_user_doc = db.collection("users").document(userId).get()
            if accepted_user_doc.exists:
                accepted_data = accepted_user_doc.to_dict()
                new_member = {
                    "uid": userId,
                    "firstName": accepted_data.get("firstName", ""),
                    "surname": accepted_data.get("surname", "")
                }
            else:
                new_member = {"uid": userId}
            project_ref.update({
                "team": ArrayUnion([new_member]),
                "teamIds": ArrayUnion([userId])
            })
            if accepted_user_doc.exists:
                accepted_data = accepted_user_doc.to_dict()
                accepted_first = accepted_data.get("firstName", "Someone")
                accepted_surname = accepted_data.get("surname", "")
            else:
                accepted_first = "Someone"
                accepted_surname = ""
            owner_notif_data = {
                "type": "project-invitation-response",
                "message": f"{accepted_first} {accepted_surname} has accepted your invitation to the project {projectName}.",
                "fromUser": {"firstName": accepted_first, "surname": accepted_surname},
                "status": "unread",
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            db.collection("users").document(ownerId).collection("notifications").document().set(owner_notif_data)
            return jsonify({"message": "Invitation accepted"}), 200
        else:
            owner_notif_data = {
                "type": "project-invitation-response",
                "message": f"{userId} has declined your invitation to the project {projectName}.",
                "status": "unread",
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            db.collection("users").document(ownerId).collection("notifications").document().set(owner_notif_data)
            return jsonify({"message": "Invitation declined"}), 200
    except Exception as e:
        print(f"🔥 ERROR in respond_project_invitation: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 18. Invite to Project Endpoint
# ---------------------------
# This endpoint sends a project invitation notification to a specified user.
@app.route('/api/invite-to-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def invite_to_project():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json()
        projectId = data.get("projectId")
        projectName = data.get("projectName")
        deadline = data.get("deadline")
        ownerId = data.get("ownerId")
        invitedUserId = data.get("invitedUserId")
        if not (projectId and projectName and deadline and ownerId and invitedUserId):
            return jsonify({"error": "Missing fields"}), 400
        owner_doc = db.collection("users").document(ownerId).get()
        owner_data = owner_doc.to_dict() if owner_doc.exists else {}
        notification_data = {
            "type": "project-invitation",
            "message": f"{owner_data.get('firstName', 'Unknown')} {owner_data.get('surname', 'User')} has invited you to join their project: {projectName}",
            "projectName": projectName,
            "deadline": deadline,
            "ownerId": ownerId,
            "fromUser": {
                "firstName": owner_data.get("firstName", "Unknown"),
                "surname": owner_data.get("surname", "User"),
                "email": owner_data.get("email", "")
            },
            "status": "unread",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "projectId": projectId
        }
        notif_ref = db.collection("users").document(invitedUserId).collection("notifications").document()
        notif_ref.set(notification_data)
        return jsonify({"message": "Project invitation sent", "invitationId": notif_ref.id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 19. Update Task Milestones Endpoint
# ---------------------------
# This endpoint updates the milestones for a given task in a project.
@app.route('/api/update-task-milestones', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_task_milestones():
    try:
        data = request.get_json()
        projectId = data.get("projectId")
        taskName = data.get("taskName")
        milestones = data.get("milestones")
        if not (projectId and taskName and milestones is not None):
            return jsonify({"error": "projectId, taskName, and milestones are required"}), 400
        project_ref = db.collection("projects").document(projectId)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        tasks = project_data.get("tasks", [])
        updated = False
        for task in tasks:
            if task.get("taskName") == taskName:
                task["milestones"] = milestones
                updated = True
                break
        if not updated:
            return jsonify({"error": "Task not found"}), 404
        project_ref.update({"tasks": tasks})
        return jsonify({"message": "Milestones updated successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in update_task_milestones: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 20. Delete Project Endpoint
# ---------------------------
# This endpoint deletes a project if the requester is the owner.
@app.route('/api/delete-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def delete_project():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        requester_id = data.get("requesterId")
        if not project_id or not requester_id:
            return jsonify({"error": "Project ID and requesterId are required"}), 400
        project_ref = db.collection("projects").document(project_id)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        if requester_id != project_data.get("ownerId"):
            return jsonify({"error": "Not authorized to delete this project"}), 403
        project_ref.delete()
        return jsonify({"message": "Project deleted successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in delete_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 20A. Leave Project Endpoint
# ---------------------------
# This endpoint allows a non-owner to leave a project and notifies remaining members.
@app.route('/api/leave-project', methods=['POST', 'OPTIONS'])
@cross_origin()
def leave_project():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        user_id = data.get("userId")
        if not project_id or not user_id:
            return jsonify({"error": "Project ID and userId are required"}), 400
        project_ref = db.collection("projects").document(project_id)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        if user_id == project_data.get("ownerId"):
            return jsonify({"error": "Project owner cannot leave the project"}), 403
        new_team = [member for member in project_data.get("team", []) if member.get("uid") != user_id]
        new_team_ids = [uid for uid in project_data.get("teamIds", []) if uid != user_id]
        project_ref.update({"team": new_team, "teamIds": new_team_ids})
        remaining_members = set()
        if project_data.get("ownerId"):
            remaining_members.add(project_data.get("ownerId"))
        for uid in new_team_ids:
            remaining_members.add(uid)
        leaving_user_doc = db.collection("users").document(user_id).get()
        if leaving_user_doc.exists:
            leaving_user_data = leaving_user_doc.to_dict()
            leaving_username = f"{leaving_user_data.get('firstName', '')} {leaving_user_data.get('surname', '')}".strip()
        else:
            leaving_username = "A user"
        notification_message = f"User {leaving_username} left project {project_data.get('projectName', 'Unknown')}."
        for member_id in remaining_members:
            notif_data = {
                "type": "project-leave",
                "message": notification_message,
                "status": "unread",
                "timestamp": firestore.SERVER_TIMESTAMP,
                "projectId": project_id,
                "projectName": project_data.get("projectName", "Unknown")
            }
            db.collection("users").document(member_id).collection("notifications").add(notif_data)
        return jsonify({"message": "Left project successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in leave_project: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 21. Add Comment Endpoint
# ---------------------------
# This endpoint adds a new comment to a project and sends notifications to relevant users.
@app.route('/api/add-comment', methods=['POST', 'OPTIONS'])
@cross_origin()
def add_comment():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        user_id = data.get("userId")
        comment_text = data.get("commentText")
        if not (project_id and user_id and comment_text):
            return jsonify({"error": "projectId, userId, and commentText are required"}), 400
        project_ref = db.collection("projects").document(project_id)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        project_name = project_data.get("projectName", "this project")
        user_doc = db.collection("users").document(user_id).get()
        username = ""
        if user_doc.exists:
            user_data = user_doc.to_dict()
            username = f"{user_data.get('firstName', '')} {user_data.get('surname', '')}".strip()
        comment_data = {
            "userId": user_id,
            "username": username,
            "commentText": comment_text,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        # Add the comment and automatically generate a document ID
        db.collection("projects").document(project_id).collection("comments").add(comment_data)
        notif_message = f"User {username} commented on project {project_name}"
        recipient_ids = set()
        owner_id = project_data.get("ownerId")
        if owner_id:
            recipient_ids.add(owner_id)
        for member_id in project_data.get("teamIds", []):
            recipient_ids.add(member_id)
        if user_id in recipient_ids:
            recipient_ids.remove(user_id)
        for rid in recipient_ids:
            notif_data = {
                "type": "comment",
                "message": notif_message,
                "fromUser": {"uid": user_id, "username": username},
                "status": "unread",
                "timestamp": firestore.SERVER_TIMESTAMP,
                "projectId": project_id,
                "projectName": project_name
            }
            db.collection("users").document(rid).collection("notifications").document().set(notif_data)
        return jsonify({"message": "Comment added and notifications sent"}), 200
    except Exception as e:
        print(f"🔥 ERROR in add_comment: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 22. Get Comments Endpoint
# ---------------------------
# This endpoint retrieves all comments for a given project, sorted by timestamp.
# (Document ID is added to each comment in this section.)
@app.route('/api/get-comments', methods=['POST', 'OPTIONS'])
@cross_origin()
def get_comments():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        if not project_id:
            return jsonify({"error": "projectId is required"}), 400
        comments_ref = db.collection("projects").document(project_id).collection("comments")
        query = comments_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        comments = []
        for doc in query:
            comment = doc.to_dict()
            comment["id"] = doc.id  # Document ID is added here for deletion reference
            comments.append(comment)
        return jsonify({"comments": comments}), 200
    except Exception as e:
        print(f"🔥 ERROR in get_comments: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 23. Get Chat Messages Endpoint
# ---------------------------
# This endpoint retrieves chat messages for a conversation, ordered by timestamp.
@app.route('/api/get-chat-messages', methods=['POST', 'OPTIONS'])
@cross_origin()
def get_chat_messages():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conversationId = data.get("conversationId")
    if not conversationId:
        userId = data.get("userId")
        connectionId = data.get("connectionId")
        if not (userId and connectionId):
            return jsonify({"error": "Either conversationId or both userId and connectionId are required"}), 400
        conversationId = '-'.join(sorted([userId, connectionId]))
    messages_ref = db.collection("conversations").document(conversationId).collection("messages")
    query = messages_ref.order_by("timestamp", direction=firestore.Query.ASCENDING).stream()
    messages = [doc.to_dict() for doc in query]
    return jsonify({"messages": messages}), 200

# ---------------------------
# 24. Send Chat Message Endpoint
# ---------------------------
# This endpoint sends a new chat message and creates a notification for the receiver.
@app.route('/api/send-chat-message', methods=['POST', 'OPTIONS'])
@cross_origin()
def send_chat_message():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    senderId = data.get("senderId")
    receiverId = data.get("receiverId")
    messageText = data.get("messageText")
    if not (senderId and receiverId and messageText):
        return jsonify({"error": "senderId, receiverId, and messageText are required"}), 400
    conversationId = '-'.join(sorted([senderId, receiverId]))
    message_data = {
        "senderId": senderId,
        "messageText": messageText,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "read": False
    }
    # Add the chat message to the conversation collection
    db.collection("conversations").document(conversationId).collection("messages").add(message_data)
    # Create a chat notification for the receiver
    notification_data = {
        "type": "chat",
        "message": f"You have a new message from {senderId}.",
        "fromUser": {},
        "status": "unread",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "conversationId": conversationId
    }
    notif_ref = db.collection("users").document(receiverId).collection("notifications").document()
    notif_ref.set(notification_data)
    return jsonify({"message": "Message sent"}), 200

# ---------------------------
# 26. Mark Messages as Read Endpoint
# ---------------------------
# This endpoint marks all messages (and related notifications) as read in a conversation for a user.
@app.route('/api/mark-messages-read', methods=['POST', 'OPTIONS'])
@cross_origin()
def mark_messages_read():
    try:
        data = request.get_json()
        conversation_id = data.get("conversationId")
        recipient_id = data.get("recipientId")
        if not conversation_id or not recipient_id:
            return jsonify({"error": "conversationId and recipientId are required"}), 400
        messages_ref = db.collection("conversations").document(conversation_id).collection("messages")
        query = messages_ref.where("receiverId", "==", recipient_id).where("read", "==", False).stream()
        batch = db.batch()
        msg_count = 0
        for msg in query:
            msg_ref = messages_ref.document(msg.id)
            batch.update(msg_ref, {"read": True})
            msg_count += 1
        batch.commit()
        # Update chat notifications as read
        notifs_ref = db.collection("users").document(recipient_id).collection("notifications")
        notif_query = notifs_ref.where("type", "==", "chat") \
                                .where("conversationId", "==", conversation_id) \
                                .where("status", "==", "unread").stream()
        notif_batch = db.batch()
        for notif in notif_query:
            notif_ref = notifs_ref.document(notif.id)
            notif_batch.update(notif_ref, {"status": "read"})
        notif_batch.commit()
        print(f"Marked {msg_count} messages and related chat notifications as read in conversation {conversation_id} for user {recipient_id}")
        return jsonify({"message": f"Marked {msg_count} messages as read"}), 200
    except Exception as e:
        print(f"🔥 ERROR in mark_messages_read: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 27. Remove Collaborator Endpoint
# ---------------------------
# This endpoint removes a collaborator from a project and sends a removal notification.
@app.route('/api/remove-collaborator', methods=['POST', 'OPTIONS'])
@cross_origin()
def remove_collaborator():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        collaborator_id = data.get("collaboratorId")
        owner_id = data.get("ownerId")
        if not (project_id and collaborator_id and owner_id):
            return jsonify({"error": "projectId, collaboratorId, and ownerId are required"}), 400
        project_ref = db.collection("projects").document(project_id)
        project_doc = project_ref.get()
        if not project_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        project_data = project_doc.to_dict()
        new_team = [member for member in project_data.get("team", []) if member.get("uid") != collaborator_id]
        new_team_ids = [uid for uid in project_data.get("teamIds", []) if uid != collaborator_id]
        project_ref.update({"team": new_team, "teamIds": new_team_ids})
        owner_doc = db.collection("users").document(owner_id).get()
        owner_name = ""
        if owner_doc.exists:
            owner_data = owner_doc.to_dict()
            owner_name = f"{owner_data.get('firstName', '')} {owner_data.get('surname', '')}".strip()
        notification_data = {
            "type": "project-removal",
            "message": f"You were removed from project {project_data.get('projectName', 'Unknown')}",
            "status": "unread",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "removedBy": owner_name
        }
        db.collection("users").document(collaborator_id).collection("notifications").document().set(notification_data)
        return jsonify({"message": "Collaborator removed successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in remove_collaborator: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 28. DELETE COMMENT Endpoint
# ---------------------------
# This endpoint deletes a comment. It checks that the required parameters are provided and that
# the user is authorized to delete the comment (i.e. is the author).
@app.route('/api/delete-comment', methods=['POST', 'OPTIONS'])
@cross_origin()
def delete_comment():
    try:
        data = request.get_json()
        project_id = data.get("projectId")
        comment_id = data.get("commentId")
        user_id = data.get("userId")
        if not (project_id and comment_id and user_id):
            return jsonify({"error": "projectId, commentId, and userId are required"}), 400
        comment_ref = db.collection("projects").document(project_id).collection("comments").document(comment_id)
        comment_doc = comment_ref.get()
        if not comment_doc.exists:
            return jsonify({"error": "Comment not found"}), 404
        comment_data = comment_doc.to_dict()
        if comment_data.get("userId") != user_id:
            return jsonify({"error": "Not authorized to delete this comment"}), 403
        comment_ref.delete()
        return jsonify({"message": "Comment deleted successfully"}), 200
    except Exception as e:
        print(f"🔥 ERROR in delete_comment: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------
# 29. Run the Flask App
# ---------------------------
# This final section starts the Flask application in debug mode.
if __name__ == "__main__":
    app.run(debug=True)
