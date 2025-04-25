# Back-End README

This back-end is a Python-based RESTful API service built with Flask and Firebase Admin SDK that powers the Final Year Project. It handles authentication, data persistence in Firestore, and real-time updates via HTTP and Firestore triggers.

## Getting Started

### Prerequisites

- **Python** (v3.8 or higher)
- **pip** (v20 or higher)

## Clone the Repo

```bash
git clone https://github.com/yourusername/your-repo.git
cd your-repo/backend
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Development Server

Start the Flask development server with hot reload:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```

The service will run by default on `http://localhost:5000`.

## Building for Production

In production, use a WSGI server such as Gunicorn:

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

## Configuration

Create a `.env` file in the `backend` directory and add the following environment variables:

```env
GOOGLE_APPLICATION_CREDENTIALS=path/to/firebase_service_key.json
FIRESTORE_EMULATOR_HOST=localhost:8080      # optional, for local emulation
```

Adjust the path to your Firebase service account key and other settings as needed.

## API Endpoints

All endpoints are prefixed with `/api`.

- **POST** `/api/create-user`  
  Registers a new user with email/password (hashed via bcrypt) and stores profile data in Firestore.
- **POST** `/api/login`  
  Verifies Firebase ID token and returns user profile.
- **POST** `/api/update-user-settings`  
  Updates non-password settings (e.g., telephone).
- **POST** `/api/update-user-password`  
  Validates and updates user password in Firebase Auth and Firestore.
- **POST** `/api/search-users`  
  Searches users by email, first name, or surname.
- **POST** `/api/send-connection-request`  
  Creates a connection request and notification.
- **POST** `/api/respond-connection-request`  
  Accepts or rejects a connection request, updates user connections.
- **POST** `/api/user-connections`  
  Retrieves a user’s connections list.
- **POST** `/api/notifications`  
  Fetches notifications, optionally filtering by type.
- **POST** `/api/dismiss-notification`  
  Deletes a notification.
- **POST** `/api/create-project`  
  Creates a new project document with tasks and metadata.
- **POST** `/api/update-project`  
  Updates project details and broadcasts status-change notifications.
- **POST** `/api/my-projects`  
  Retrieves projects owned by or shared with the user.
- **POST** `/api/get-project`  
  Fetches detailed data for a specific project.
- **POST** `/api/project-deadlines`  
  Lists project deadlines for a user.
- **POST** `/api/invite-to-project`  
  Sends a project invitation notification.
- **POST** `/api/respond-project-invitation`  
  Accepts or declines a project invitation and updates team membership.
- **POST** `/api/update-task-milestones`  
  Updates milestones for a project task.
- **POST** `/api/delete-project`  
  Deletes a project if requested by owner.
- **POST** `/api/leave-project`  
  Allows a team member to leave a project and notifies remaining members.
- **POST** `/api/add-comment`  
  Adds a comment to a project and notifies team.
- **POST** `/api/get-comments`  
  Retrieves comments sorted by timestamp.
- **POST** `/api/get-chat-messages`  
  Retrieves messages for a conversation.
- **POST** `/api/send-chat-message`  
  Sends a message and notifies the recipient.
- **POST** `/api/mark-messages-read`  
  Marks chat messages and notifications as read.
- **POST** `/api/remove-collaborator`  
  Removes a collaborator and sends removal notification.
- **POST** `/api/delete-comment`  
  Deletes a comment if the requester is its author.

## Features

- **Flask**: Lightweight microframework for building APIs.
- **Firebase Admin SDK**: Manages Auth, Firestore, and realtime updates.
- **bcrypt**: Secure password hashing.
- **CORS**: Enabled globally for cross-origin requests.
- **Structured Logging**: Console logging for request tracing and error handling.

## Deployment

### Docker

```bash
docker build -t my-backend .
docker run -d -p 5000:5000 --env-file .env my-backend
```

### Cloud Functions

You can also deploy individual endpoints as Cloud Functions using Firebase:

```bash
firebase deploy --only functions
```
