import os
import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional

import traceback
import resend
import razorpay
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

import firebase_admin.auth as fb_auth
from database import db, licenses_col, usage_logs_col, payments_col
from license_utils import (
    generate_license_key,
    hash_key,
    calculate_expiry,
    get_plan_features,
    get_app_limit,
)
from email_service import send_license_key_email, send_trial_expiry_warning

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@tejasai.io")

# ── App setup ─────────────────────────────────────────────────
app = FastAPI(
    title="TejasAI License API",
    description="License key generation, validation, and management for Ultra Secure Flutter Kit",
    version="1.0.0",
)

# ── Global exception handler — surfaces real errors in logs ───
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error on {request.method} {request.url.path}:")
    print(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# ── CORS ──────────────────────────────────────────────────────
# allow_origins=["*"] cannot be combined with allow_credentials=True in Starlette;
# use allow_origin_regex instead — testing mode, restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # testing mode — restrict later in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Razorpay client ───────────────────────────────────────────
rzp = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID", ""),
        os.getenv("RAZORPAY_KEY_SECRET", ""),
    )
)


# ── Generate temp password ──────────────────────────────────
def generate_temp_password() -> str:
    import secrets as _secrets, string as _string
    chars = _string.ascii_letters + _string.digits
    p1 = ''.join(_secrets.choice(chars) for _ in range(4))
    p2 = ''.join(_secrets.choice(chars) for _ in range(4))
    return f"USK-{p1}-{p2}"


# ── Create Firebase Auth user for admin panel ───────────────
def create_admin_user(email: str, name: str = "", plan: str = "trial") -> str:
    temp_password = generate_temp_password()

    try:
        fb_auth.create_user(
            email=email,
            password=temp_password,
            email_verified=True,
            display_name=name or email,
        )
    except fb_auth.EmailAlreadyExistsError:
        user = fb_auth.get_user_by_email(email)
        fb_auth.update_user(user.uid, password=temp_password)

    db.collection("dashboard_users").document(email).set({
        "email":              email,
        "name":               name or "",
        "plan":               plan,
        "mustChangePassword": True,
        "createdAt":          datetime.utcnow().isoformat(),
        "passwordChangedAt":  None,
    }, merge=True)

    return temp_password


# ── Welcome email: license key + admin credentials ──────────
def send_welcome_email_with_credentials(
    to_email: str,
    license_key: str,
    plan: str,
    buyer_name: str,
    temp_password: str,
    expires_at: str = "",
) -> bool:
    plan_label = plan.upper()
    name_line = f"Hi {buyer_name}," if buyer_name else "Hi there,"
    admin_url = os.getenv("ADMIN_PANEL_URL", "http://localhost:3000")

    try:
        resend.Emails.send({
            "from": f"TejasAI <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "Your Ultra Secure Kit — License Key + Dashboard Access",
            "html": f"""
<div style="font-family:Arial,sans-serif;background:#04080f;color:#f0e6c8;padding:40px 24px;max-width:560px;margin:0 auto;">

  <div style="text-align:center;margin-bottom:32px;">
    <div style="background:#ffb800;width:48px;height:48px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#04080f;">T</div>
    <h1 style="color:#f0e6c8;font-size:20px;margin:12px 0 0;">Tejas<span style="color:#ffb800;">AI</span></h1>
  </div>

  <div style="background:#0c1528;border:1px solid rgba(255,184,0,.2);border-radius:12px;padding:32px;">
    <p style="color:#9a8a6a;margin:0 0 6px;font-size:14px;">{name_line}</p>
    <p style="color:#f0e6c8;margin:0 0 28px;font-size:15px;">Your <strong style="color:#ffb800;">{plan_label} plan</strong> is now active.</p>

    <p style="color:#9a8a6a;font-size:11px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.08em;">Step 1 — Plugin License Key</p>
    <div style="background:#04080f;border:1px solid rgba(255,184,0,.3);border-radius:8px;padding:18px;text-align:center;margin-bottom:24px;">
      <p style="font-family:monospace;font-size:22px;font-weight:700;color:#ffb800;letter-spacing:3px;margin:0;">{license_key}</p>
    </div>

    <p style="color:#9a8a6a;font-size:11px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.08em;">Step 2 — Admin Dashboard Login</p>
    <div style="background:#04080f;border:1px solid rgba(124,106,247,.3);border-radius:8px;padding:18px;margin-bottom:16px;">
      <table style="width:100%;font-size:14px;border-collapse:collapse;">
        <tr>
          <td style="color:#9a8a6a;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05);">Website</td>
          <td style="text-align:right;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05);">
            <a href="{admin_url}/login" style="color:#7c6af7;">{admin_url}</a>
          </td>
        </tr>
        <tr>
          <td style="color:#9a8a6a;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05);">Email</td>
          <td style="text-align:right;padding:6px 0;color:#f0e6c8;">{to_email}</td>
        </tr>
        <tr>
          <td style="color:#9a8a6a;padding:6px 0;">Temp Password</td>
          <td style="text-align:right;padding:6px 0;">
            <code style="background:#1a1a35;color:#ffb800;padding:4px 10px;border-radius:4px;font-size:15px;font-weight:700;">{temp_password}</code>
          </td>
        </tr>
      </table>
    </div>

    <a href="{admin_url}/login" style="display:block;background:#7c6af7;color:white;padding:13px;border-radius:8px;text-decoration:none;font-weight:700;text-align:center;font-size:15px;">
      Open Admin Dashboard →
    </a>
    <p style="color:#9a8a6a;font-size:11px;text-align:center;margin:10px 0 0;">
      You will be asked to change your password on first login
    </p>
  </div>

  <p style="text-align:center;font-size:11px;color:#4a4030;margin-top:24px;">
    TejasAI · support@tejasai.io
  </p>
</div>
            """,
        })
        return True
    except Exception as e:
        print(f"Welcome email failed: {e}")
        return False


PAID_PLANS = ['indie', 'pro', 'enterprise']


def _create_placeholder_app(email: str, plan: str, key_prefix: str):
    """Create a placeholder app entry — one per owner, idempotent."""
    try:
        # Don't create if any app (placeholder or real) already exists for this owner
        existing = list(db.collection('apps')
            .where('ownerEmail', '==', email)
            .limit(1).get())
        if existing:
            print(f"[LICENSE] App already exists for {email}, skipping placeholder")
            return
        db.collection('apps').add({
            'ownerEmail':    email,
            'bundleId':      '',
            'appName':       'My App',
            'platform':      'unknown',
            'isActive':      True,
            'licenseKey':    key_prefix,
            'plan':          plan,
            'isPlaceholder': True,
            'addedAt':       datetime.utcnow().isoformat(),
        })
        print(f"[LICENSE] Placeholder app created for {email}")
    except Exception as e:
        print(f"[LICENSE] Placeholder app creation failed: {e}")


def get_all_features() -> list:
    return [
        "root_detection", "jailbreak_detection", "emulator_detection",
        "debugger_detection", "secure_storage", "encryption",
        "input_sanitization", "secure_random", "mitm_detection",
        "frida_detection", "xposed_detection", "vpn_detection",
        "proxy_detection", "ssl_pinning", "screenshot_blocking",
        "usb_detection", "developer_mode_detection", "biometric_auth",
        "device_fingerprint", "app_signature_verification",
        "app_integrity_check", "anti_tampering", "anti_reverse_engineering",
        "real_time_threat_stream", "behavior_monitoring", "security_metrics",
        "remote_lock", "remote_wipe", "threat_reporting", "secure_api_calls",
    ]


# ══════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════

class TrialRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = ""

class ValidateRequest(BaseModel):
    license_key: str
    bundle_id: str           # e.g. com.company.myapp
    platform: str            # android | ios | web | macos | linux | windows
    plugin_version: str = "1.0.0"

class CreateLicenseRequest(BaseModel):
    email: EmailStr
    plan: str                # free | pro | enterprise
    billing: str = "monthly" # monthly | annual
    name: Optional[str] = ""
    bundle_ids: Optional[list[str]] = []

class LicenseStatusRequest(BaseModel):
    license_key: str

class ThreatReportRequest(BaseModel):
    bundle_id: str
    threat_type: str
    threat_level: str
    timestamp: Optional[str] = ""
    device: Optional[dict] = {}
    network: Optional[dict] = {}
    attack_details: Optional[dict] = {}
    license_key: Optional[str] = ""

class PollCommandsRequest(BaseModel):
    license_key: str
    bundle_id: str

class SendCommandRequest(BaseModel):
    bundle_id:  str
    type:       str  # wipe_data | lock_app | show_alert | unlock_app
    license_key: Optional[str] = ""
    reason:     Optional[str] = ""
    message:    Optional[str] = ""
    device_id:  Optional[str] = ""


# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "service": "TejasAI License API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# ── 1. FREE TRIAL — REMOVED ───────────────────────────────────
@app.post("/trial")
async def start_free_trial():
    raise HTTPException(
        status_code=410,
        detail="Free trial is no longer available. Please purchase a plan at tejasai.io"
    )


# ── 2. VALIDATE LICENSE ───────────────────────────────────────
@app.post("/validate-license")
async def validate_license(body: ValidateRequest):
    """
    Called by the Flutter plugin on every app startup.
    Checks if license is valid, active, and not expired.
    Returns features dict so plugin knows what to enable.
    """
    print(f"[VALIDATE] key={body.license_key[:8]}... bundle={body.bundle_id}")

    key_hash = hash_key(body.license_key)
    print(f"[VALIDATE] key_hash={key_hash[:16]}...")

    results = licenses_col.where("key_hash", "==", key_hash).limit(1).get()
    docs = list(results)
    print(f"[VALIDATE] found {len(docs)} license(s)")

    if not docs:
        print("[VALIDATE] License not found")
        return {"valid": False, "reason": "invalid_key", "message": "Invalid license key"}

    doc = docs[0]
    data = doc.to_dict()
    print(f"[VALIDATE] License found: email={data.get('email')} plan={data.get('plan')}")

    # Paid plans only
    plan = data.get("plan", "")
    print(f"[VALIDATE] Plan check: {plan} in {PAID_PLANS} = {plan in PAID_PLANS}")
    if plan not in PAID_PLANS:
        return {
            "valid": False,
            "reason": "paid_plan_required",
            "message": "Please purchase a plan to use Ultra Secure Flutter Kit",
            "features": [],
            "plan": plan,
        }

    # Check status
    if data.get("status") != "active":
        return {"valid": False, "reason": "inactive", "message": "License is inactive or cancelled"}

    # Check expiry
    expires_at = data.get("expires_at")
    if expires_at:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        exp = expires_at
        if hasattr(exp, 'tzinfo') and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            doc.reference.update({"status": "expired"})
            return {"valid": False, "reason": "expired", "message": "License expired. Please renew."}

    # Check bundle ID
    bundle_id = body.bundle_id
    bundle_ids = data.get("bundle_ids", [])
    app_limit = data.get("app_limit", 1)
    print(f"[VALIDATE] bundle_ids={bundle_ids} app_limit={app_limit}")

    if bundle_id not in bundle_ids:
        print(f"[VALIDATE] New bundle_id. limit={app_limit} current={len(bundle_ids)}")
        if len(bundle_ids) >= app_limit:
            print("[VALIDATE] App limit reached!")
            return {
                "valid": False,
                "reason": "app_limit_reached",
                "message": f"App limit reached. This plan allows {app_limit} app(s). Contact support to upgrade.",
            }
        bundle_ids.append(bundle_id)
        doc.reference.update({"bundle_ids": bundle_ids})
        print(f"[VALIDATE] Added bundle_id to license")

    # Ensure app is registered — one doc per owner+bundle, idempotent
    try:
        owner_email = data.get('email', '')

        # Check if a real (non-placeholder) app doc already exists for this bundle
        existing_real = list(db.collection('apps')
            .where('ownerEmail', '==', owner_email)
            .where('bundleId', '==', bundle_id)
            .limit(1).get())

        if not existing_real:
            # Check for placeholder to upgrade
            placeholder_apps = list(db.collection('apps')
                .where('ownerEmail', '==', owner_email)
                .where('isPlaceholder', '==', True)
                .limit(1).get())

            if placeholder_apps:
                # Upgrade placeholder in-place
                placeholder_apps[0].reference.update({
                    'bundleId':      bundle_id,
                    'appName':       bundle_id.split('.')[-1].title(),
                    'platform':      body.platform,
                    'isPlaceholder': False,
                    'firstSeenAt':   datetime.utcnow().isoformat(),
                })
                print(f"[VALIDATE] Placeholder upgraded: {bundle_id}")
            else:
                # No placeholder — create fresh app doc
                db.collection('apps').add({
                    'ownerEmail':    owner_email,
                    'bundleId':      bundle_id,
                    'appName':       bundle_id.split('.')[-1].title(),
                    'platform':      body.platform,
                    'isActive':      True,
                    'licenseKey':    body.license_key[:8],
                    'plan':          plan,
                    'isPlaceholder': False,
                    'addedAt':       datetime.utcnow().isoformat(),
                })
                print(f"[VALIDATE] New app registered: {bundle_id}")
        else:
            print(f"[VALIDATE] App already registered: {bundle_id}")
    except Exception:
        print(f"[VALIDATE] App registration FAILED: {traceback.format_exc()}")

    # Log usage — deduplicate by license+bundle+day to avoid spam
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_doc_id = f"{doc.id}_{bundle_id}_{today}"
        usage_logs_col.document(log_doc_id).set({
            "license_id": doc.id,
            "bundle_id": bundle_id,
            "platform": body.platform,
            "plugin_version": body.plugin_version,
            "timestamp": datetime.utcnow(),
        })
    except Exception:
        pass

    return {
        "valid": True,
        "plan": plan,
        "features": get_all_features(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "app_limit": app_limit,
        "registered_apps": len(bundle_ids),
        "message": "License valid",
    }


# ── 3. RAZORPAY WEBHOOK ───────────────────────────────────────
@app.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str = Header(None),
):
    """
    Called automatically by Razorpay when payment succeeds.
    Generates license key and emails it to the buyer.
    """
    body_bytes = await request.body()

    # Verify webhook signature
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    expected_sig = hmac.new(
        webhook_secret.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, x_razorpay_signature or ""):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(body_bytes)
    event = payload.get("event", "")

    # Handle subscription payment
    if event == "subscription.charged":
        sub = payload["payload"]["subscription"]["entity"]
        payment = payload["payload"]["payment"]["entity"]

        plan = _get_plan_from_razorpay_plan(sub.get("plan_id", ""))
        billing = "annual" if "annual" in sub.get("plan_id", "").lower() else "monthly"
        email = payment.get("email", "")
        name = payment.get("description", "") or ""
        payment_id = payment.get("id", "")

        if not email:
            return {"received": True, "action": "skipped_no_email"}

        # Check if license already exists for this subscription
        existing = licenses_col.where("razorpay_subscription_id", "==", sub["id"]).limit(1).get()
        if list(existing):
            return {"received": True, "action": "already_processed"}

        # Generate license
        key = generate_license_key(plan=plan)
        key_hash = hash_key(key)
        expires_at = calculate_expiry(plan, billing)
        features = get_plan_features(plan)

        license_data = {
            "key_hash": key_hash,
            "key_prefix": key[:8],
            "email": email.lower(),
            "name": name,
            "plan": plan,
            "billing": billing,
            "status": "active",
            "bundle_ids": [],
            "app_limit": get_app_limit(plan),
            "features": features,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "trial": False,
            "payment_id": payment_id,
            "razorpay_subscription_id": sub["id"],
        }
        license_ref = licenses_col.document()
        license_ref.set(license_data)
        _create_placeholder_app(email.lower(), plan, key[:8])

        # Save payment record
        payments_col.document().set({
            "license_id": license_ref.id,
            "payment_id": payment_id,
            "amount": payment.get("amount", 0) / 100,
            "currency": payment.get("currency", "INR"),
            "email": email,
            "plan": plan,
            "billing": billing,
            "timestamp": datetime.utcnow(),
        })

        # Email in background
        background_tasks.add_task(
            send_license_key_email,
            to_email=email,
            license_key=key,
            plan=plan,
            buyer_name=name,
            expires_at=expires_at.strftime("%d %b %Y") if expires_at else "",
        )

        return {"received": True, "action": "license_created", "plan": plan}

    # Handle subscription cancellation
    elif event == "subscription.cancelled":
        sub_id = payload["payload"]["subscription"]["entity"]["id"]
        results = licenses_col.where("razorpay_subscription_id", "==", sub_id).limit(1).get()
        for doc in results:
            doc.reference.update({"status": "cancelled"})
        return {"received": True, "action": "license_cancelled"}

    return {"received": True, "action": "event_ignored"}


# ── 4. MANUAL CREATE LICENSE (admin use) ─────────────────────
@app.post("/admin/create-license")
async def create_license_manual(
    body: CreateLicenseRequest,
    background_tasks: BackgroundTasks,
    x_admin_secret: str = Header(None),
):
    """
    Manually create a license. Use for enterprise deals.
    Protected by admin secret header.
    """
    if x_admin_secret != os.getenv("APP_SECRET_KEY", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if body.plan not in PAID_PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {PAID_PLANS}")

    key = generate_license_key(plan=body.plan)
    key_hash = hash_key(key)
    expires_at = calculate_expiry(body.plan, body.billing)
    features = get_all_features()

    license_data = {
        "key_hash": key_hash,
        "key_prefix": key[:8],
        "email": body.email.lower(),
        "name": body.name or "",
        "plan": body.plan,
        "billing": body.billing,
        "status": "active",
        "bundle_ids": body.bundle_ids or [],
        "app_limit": get_app_limit(body.plan),
        "features": features,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "trial": False,
        "payment_id": "manual",
        "razorpay_subscription_id": None,
    }
    license_ref = licenses_col.document()
    license_ref.set(license_data)
    _create_placeholder_app(body.email.lower(), body.plan, key[:8])

    background_tasks.add_task(
        send_license_key_email,
        to_email=body.email,
        license_key=key,
        plan=body.plan,
        buyer_name=body.name or "",
        expires_at=expires_at.strftime("%d %b %Y") if expires_at else "",
    )

    return {
        "success": True,
        "license_key": key,
        "plan": body.plan,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


# ── 5. LICENSE STATUS ─────────────────────────────────────────
@app.post("/license-status")
async def license_status(body: LicenseStatusRequest):
    """Check status of a license key (for user dashboard)."""
    key_hash = hash_key(body.license_key)
    results = licenses_col.where("key_hash", "==", key_hash).limit(1).get()
    docs = list(results)

    if not docs:
        raise HTTPException(status_code=404, detail="License not found")

    data = docs[0].to_dict()
    expires_at = data.get("expires_at")

    return {
        "plan": data.get("plan"),
        "status": data.get("status"),
        "billing": data.get("billing"),
        "email": data.get("email"),
        "bundle_ids": data.get("bundle_ids", []),
        "app_limit": data.get("app_limit", 1),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "trial": data.get("trial", False),
        "features": data.get("features", {}),
    }


# ── 6. REVOKE LICENSE (admin) ─────────────────────────────────
@app.delete("/admin/revoke-license")
async def revoke_license(
    body: LicenseStatusRequest,
    x_admin_secret: str = Header(None),
):
    """Revoke a license key. Admin only."""
    if x_admin_secret != os.getenv("APP_SECRET_KEY", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    key_hash = hash_key(body.license_key)
    results = licenses_col.where("key_hash", "==", key_hash).limit(1).get()
    docs = list(results)

    if not docs:
        raise HTTPException(status_code=404, detail="License not found")

    docs[0].reference.update({"status": "revoked"})
    return {"success": True, "message": "License revoked"}


# ── 7. RECEIVE THREAT REPORT FROM PLUGIN ─────────────────────
@app.post("/v1/threat-report")
async def receive_threat_report(body: ThreatReportRequest):
    """Receive threat reports from Flutter plugin"""
    try:
        device = body.device or {}
        db.collection("threat_reports").add({
            "bundle_id":      body.bundle_id,
            "threat_type":    body.threat_type,
            "threat_level":   body.threat_level,
            "device":         device,
            "device_id":      device.get("device_id", ""),
            "device_model":   device.get("model", "unknown"),
            "network":        body.network or {},
            "attack_details": body.attack_details or {},
            "timestamp":      body.timestamp,
            "received_at":    datetime.utcnow().isoformat(),
            "status":         "new",
            "owner_email":    body.license_key or "",
        })
        return {"received": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 8. PLUGIN POLLS FOR ADMIN COMMANDS ───────────────────────
@app.post("/v1/commands")
async def get_pending_commands(body: dict):
    """Called by plugin to check for pending admin commands."""
    bundle_id = body.get("bundle_id", "")
    device_id = body.get("device_id", "")

    commands_ref = (
        db.collection("admin_commands")
        .where("bundle_id", "==", bundle_id)
        .where("status", "==", "pending")
        .stream()
    )

    result = []
    for cmd in commands_ref:
        data = cmd.to_dict()
        cmd_device_id = data.get("device_id", "")

        # If command targets a specific device, skip other devices
        if cmd_device_id and cmd_device_id != device_id:
            continue

        result.append({"id": cmd.id, **data})
        cmd.reference.update({"status": "delivered"})

    return {"commands": result}


# ── 9. ADMIN SENDS COMMAND TO APP ────────────────────────────
@app.post("/v1/admin/send-command")
async def send_command(
    body: SendCommandRequest,
    x_admin_secret: str = Header(None),
):
    """Admin sends a remote command to an app. Requires x-admin-secret."""
    if x_admin_secret != os.getenv("APP_SECRET_KEY", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    db.collection("admin_commands").add({
        "bundle_id":  body.bundle_id,
        "type":       body.type,
        "reason":     body.reason or "",
        "message":    body.message or "",
        "device_id":  body.device_id or "",
        "target":     "specific_device" if body.device_id else "all_devices",
        "status":     "pending",
        "created_at": datetime.utcnow().isoformat(),
    })
    return {"success": True}


# ── 10. HEALTH CHECK ──────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── 8. TEST — create license without payment ──────────────────
class TestLicenseRequest(BaseModel):
    email: EmailStr
    name: str = ""
    plan: str = "indie"

@app.post("/test/create-license")
async def test_create_license(
    body: TestLicenseRequest,
    background_tasks: BackgroundTasks,
    x_admin_secret: str = Header(None),
):
    """TESTING ONLY — creates license without payment. Requires x-admin-secret header."""
    if x_admin_secret != os.getenv("APP_SECRET_KEY", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    email = body.email.lower().strip()

    existing = licenses_col.where("email", "==", email).limit(1).get()
    if list(existing):
        raise HTTPException(status_code=400, detail="License already exists for this email")

    key        = generate_license_key(plan=body.plan)
    key_hash   = hash_key(key)
    expires_at = calculate_expiry(body.plan)
    features   = get_plan_features(body.plan)

    license_data = {
        "key_hash":   key_hash,
        "key_prefix": key[:8],
        "email":      email,
        "name":       body.name,
        "plan":       body.plan,
        "billing":    "monthly",
        "status":     "active",
        "bundle_ids": [],
        "app_limit":  get_app_limit(body.plan),
        "features":   features,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "trial":      True,
        "payment_id": "test_mode",
    }
    license_ref = licenses_col.document()
    license_ref.set(license_data)
    _create_placeholder_app(email, body.plan, key[:8])

    temp_password = create_admin_user(
        email=email,
        name=body.name,
        plan=body.plan,
    )

    background_tasks.add_task(
        send_welcome_email_with_credentials,
        to_email=email,
        license_key=key,
        plan=body.plan,
        buyer_name=body.name,
        temp_password=temp_password,
        expires_at=expires_at.strftime("%d %b %Y") if expires_at else "",
    )

    return {
        "success":       True,
        "license_key":   key,
        "temp_password": temp_password,
        "email":         email,
        "plan":          body.plan,
        "note":          "TEST MODE — email sent in background",
    }


# ── Helper ────────────────────────────────────────────────────
def _get_plan_from_razorpay_plan(plan_id: str) -> str:
    """
    Map Razorpay plan ID to our plan name.
    Set these in your Razorpay dashboard and update here.
    Example: plan_pro_monthly, plan_pro_annual, plan_enterprise
    """
    plan_id = plan_id.lower()
    if "enterprise" in plan_id:
        return "enterprise"
    elif "pro" in plan_id:
        return "pro"
    return "pro"  # default
