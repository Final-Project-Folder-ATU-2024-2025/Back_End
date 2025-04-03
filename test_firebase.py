import firebase_admin
from firebase_admin import credentials

# ===============================================================
# Initialize Firebase Admin SDK
# ---------------------------------------------------------------
# This section attempts to load the service account key from a 
# JSON file and initialize the Firebase Admin SDK with it.
# The service account key provides secure access to Firebase 
# services from the backend.
# ===============================================================
try:
    # Load the service account key from the JSON file.
    cred = credentials.Certificate("firebase_service_key.json")
    
    # Initialize the Firebase Admin SDK with the loaded credentials.
    firebase_admin.initialize_app(cred)
    
    # Print a success message if initialization is successful.
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    # If there is an error during initialization, print the error message.
    print(f"🔥 ERROR: {str(e)}")
