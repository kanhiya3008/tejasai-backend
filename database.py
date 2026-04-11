import os
import base64
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# ── Initialize Firebase ───────────────────────────────────────
def _init_firebase():
    if firebase_admin._apps:
        return

    cred_b64 = os.getenv("FIREBASE_CREDENTIALS_B64")

    try:
        if cred_b64:
            # Production (Railway): decode base64 → write to temp file → load
            decoded = base64.b64decode(cred_b64)
            with open("/tmp/firebase.json", "wb") as f:
                f.write(decoded)
            cred = credentials.Certificate("/tmp/firebase.json")
        else:
            # Local development: load from file path
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
            cred = credentials.Certificate(cred_path)

        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")

    except Exception as e:
        print("Firebase init failed:", str(e))
        raise e

_init_firebase()

# ── Firestore client ──────────────────────────────────────────
# db = firestore.client()
db = firestore.client()

# ── Collection references ─────────────────────────────────────
licenses_col    = db.collection("licenses")
usage_logs_col  = db.collection("usage_logs")
trials_col      = db.collection("trials")
payments_col    = db.collection("payments")
