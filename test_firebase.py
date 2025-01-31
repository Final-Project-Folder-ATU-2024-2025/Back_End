import firebase_admin
from firebase_admin import credentials

# Try loading the service account key directly
try:
    cred = credentials.Certificate("firebase_service_key.json")
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    print(f"🔥 ERROR: {str(e)}")
