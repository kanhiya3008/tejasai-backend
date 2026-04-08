import secrets
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional


# ── Key format: USK-XXXX-XXXX-XXXX ──────────────────────────
def generate_license_key(plan: str = "pro") -> str:
    """
    Generate a unique license key.
    Format: USK-A1B2-C3D4-E5F6
    """
    chars = string.ascii_uppercase + string.digits
    segments = [
        ''.join(secrets.choice(chars) for _ in range(4))
        for _ in range(3)
    ]
    prefix = "USK"  # UltraSecureKit
    if plan == "trial":
        prefix = "TRL"
    elif plan == "enterprise":
        prefix = "ENT"

    return f"{prefix}-{'-'.join(segments)}"


def hash_key(key: str) -> str:
    """Hash the license key before storing in Firebase."""
    return hashlib.sha256(key.encode()).hexdigest()


def calculate_expiry(plan: str, billing: str = "monthly") -> Optional[datetime]:
    """
    Calculate expiry date based on plan and billing cycle.
    Returns None for enterprise (custom handled manually).
    """
    now = datetime.utcnow()

    if plan == "trial":
        return now + timedelta(days=14)
    elif plan == "free":
        return None  # Never expires
    elif plan == "pro":
        if billing == "annual":
            return now + timedelta(days=365)
        else:
            return now + timedelta(days=30)
    elif plan == "enterprise":
        return now + timedelta(days=365)  # Default 1 year, can be extended
    return now + timedelta(days=30)


def get_plan_features(plan: str) -> dict:
    """
    Return which features are unlocked per plan.
    Plugin reads this to enable/disable features.
    """
    base = {
        "root_detection": "basic",
        "jailbreak_detection": "basic",
        "emulator_detection": True,
        "debugger_detection": True,
        "developer_mode_detection": True,
        "screenshot_protection": True,
        "app_signature_verification": True,
        "install_source_check": True,
        "aes_256_storage": True,
        "ssl_pinning": "1_cert",
        "security_mode": "monitor",
        # Pro features — locked on free
        "frida_detection": False,
        "xposed_detection": False,
        "mitm_detection": False,
        "proxy_detection": False,
        "vpn_detection": False,
        "rasp": False,
        "app_integrity_checks": False,
        "biometric_vault": False,
        "data_ttl": False,
        "ai_monitoring": False,
        "device_risk_scoring": False,
        "threat_stream": False,
        "usb_detection": False,
        "unlimited_ssl": False,
        # Enterprise only
        "custom_rules": False,
        "white_label": False,
        "owasp_report": False,
    }

    if plan in ("trial", "pro", "enterprise"):
        base.update({
            "root_detection": "full",
            "jailbreak_detection": "full",
            "ssl_pinning": "unlimited",
            "security_mode": "strict",
            "frida_detection": True,
            "xposed_detection": True,
            "mitm_detection": True,
            "proxy_detection": True,
            "vpn_detection": True,
            "rasp": True,
            "app_integrity_checks": True,
            "biometric_vault": True,
            "data_ttl": True,
            "ai_monitoring": True,
            "device_risk_scoring": True,
            "threat_stream": True,
            "usb_detection": True,
            "unlimited_ssl": True,
        })

    if plan == "enterprise":
        base.update({
            "custom_rules": True,
            "white_label": True,
            "owasp_report": True,
        })

    return base


def get_app_limit(plan: str) -> int:
    """How many apps can use this license key."""
    limits = {
        "free": 1,
        "trial": 3,
        "pro": 3,
        "enterprise": 9999,  # unlimited
    }
    return limits.get(plan, 1)
