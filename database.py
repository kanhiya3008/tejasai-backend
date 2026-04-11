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
            # Production (Railway)
            decoded = base64.b64decode(cred_b64)
            temp_path = "/tmp/firebase.json"

            with open(temp_path, "wb") as f:
                f.write(decoded)

            cred = credentials.Certificate(temp_path)

        else:
            # Local development
            cred_path = os.getenv(
                "FIREBASE_CREDENTIALS_PATH",
                "firebase-credentials.json"
            )
            cred = credentials.Certificate(cred_path)

        # Initialize Firebase
        firebase_admin.initialize_app(cred)

        # ✅ Force correct project binding (VERY IMPORTANT)
        os.environ["GOOGLE_CLOUD_PROJECT"] = cred.project_id

        print(f"✅ Firebase initialized for project: {cred.project_id}")

    except Exception as e:
        print("❌ Firebase init failed:", str(e))
        raise e


# Initialize Firebase
_init_firebase()

# ── Firestore client (FINAL FIX) ──────────────────────────────
try:
    db = firestore.client()   # ✅ DO NOT pass project or database
    print("✅ Firestore client connected")

except Exception as e:
    print("❌ Firestore client error:", str(e))
    raise e


# ── Collection references ─────────────────────────────────────
licenses_col   = db.collection("licenses")
usage_logs_col = db.collection("usage_logs")
trials_col     = db.collection("trials")
payments_col   = db.collection("payments")