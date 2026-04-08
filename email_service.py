import os
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@tejasai.io")


def send_license_key_email(
    to_email: str,
    license_key: str,
    plan: str,
    buyer_name: str = "",
    expires_at: str = "",
) -> bool:
    """Send license key email after successful payment or trial signup."""
    plan_label = plan.upper()
    name_line = f"Hi {buyer_name}," if buyer_name else "Hi there,"

    try:
        resend.Emails.send({
            "from": f"TejasAI <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"🔐 Your TejasAI License Key — {plan_label} Plan",
            "html": f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="font-family:Arial,sans-serif;background:#04080f;color:#f0e6c8;margin:0;padding:0;">
  <div style="max-width:560px;margin:0 auto;padding:40px 24px;">

    <!-- Header -->
    <div style="text-align:center;margin-bottom:32px;">
      <div style="background:#ffb800;width:48px;height:48px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#04080f;">T</div>
      <h1 style="font-size:20px;font-weight:700;margin:12px 0 0;color:#f0e6c8;">Tejas<span style="color:#ffb800;">AI</span></h1>
    </div>

    <!-- Main card -->
    <div style="background:#0c1528;border:1px solid rgba(255,184,0,.2);border-radius:12px;padding:32px;">
      <p style="margin:0 0 8px;font-size:15px;color:#9a8a6a;">{name_line}</p>
      <p style="margin:0 0 24px;font-size:15px;color:#f0e6c8;">Your <strong style="color:#ffb800;">{plan_label} plan</strong> license key is ready. Copy it and add it to your Flutter app.</p>

      <!-- License key box -->
      <div style="background:#04080f;border:1px solid rgba(255,184,0,.3);border-radius:8px;padding:20px;text-align:center;margin-bottom:24px;">
        <p style="font-family:monospace;font-size:22px;font-weight:700;color:#ffb800;letter-spacing:3px;margin:0;">{license_key}</p>
      </div>

      <!-- How to use -->
      <p style="font-size:13px;color:#9a8a6a;margin:0 0 12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">How to use</p>
      <div style="background:#111e35;border-radius:6px;padding:16px;font-family:monospace;font-size:13px;color:#7fb3cc;margin-bottom:24px;">
        <span style="color:#a78bfa;">await</span> UltraSecureFlutterKit().<span style="color:#38bdf8;">initializeSecureMonitor</span>(<br/>
        &nbsp;&nbsp;SecurityConfig(...),<br/>
        &nbsp;&nbsp;<span style="color:#a78bfa;">licenseKey</span>: <span style="color:#22c55e;">'{license_key}'</span>,<br/>
        );
      </div>

      <!-- Plan details -->
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr>
          <td style="padding:8px 0;color:#9a8a6a;border-bottom:1px solid rgba(255,184,0,.08);">Plan</td>
          <td style="padding:8px 0;color:#f0e6c8;text-align:right;border-bottom:1px solid rgba(255,184,0,.08);">{plan_label}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#9a8a6a;border-bottom:1px solid rgba(255,184,0,.08);">App licenses</td>
          <td style="padding:8px 0;color:#f0e6c8;text-align:right;border-bottom:1px solid rgba(255,184,0,.08);">{'3 apps' if plan in ('pro','trial') else '1 app' if plan == 'free' else 'Unlimited'}</td>
        </tr>
        {"<tr><td style='padding:8px 0;color:#9a8a6a;'>Expires</td><td style='padding:8px 0;color:#f0e6c8;text-align:right;'>" + expires_at + "</td></tr>" if expires_at else ""}
      </table>
    </div>

    <!-- Links -->
    <div style="text-align:center;margin-top:24px;">
      <a href="https://pub.dev/packages/ultra_secure_flutter_kit" style="display:inline-block;background:#ffb800;color:#04080f;font-size:13px;font-weight:700;padding:11px 24px;border-radius:6px;text-decoration:none;margin-right:8px;">View on pub.dev</a>
      <a href="https://tejasai.io/security" style="display:inline-block;border:1px solid rgba(255,184,0,.3);color:#ffb800;font-size:13px;padding:11px 24px;border-radius:6px;text-decoration:none;">Documentation</a>
    </div>

    <!-- Footer -->
    <p style="text-align:center;font-size:11px;color:#4a4030;margin-top:32px;">
      TejasAI · Gurgaon, India · <a href="mailto:support@tejasai.io" style="color:#4a4030;">support@tejasai.io</a>
    </p>
  </div>
</body>
</html>
""",
        })
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


def send_trial_expiry_warning(to_email: str, license_key: str, days_left: int) -> bool:
    """Send reminder 3 days before trial expires."""
    try:
        resend.Emails.send({
            "from": f"TejasAI <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"⚠️ Your TejasAI trial expires in {days_left} days",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#04080f;color:#f0e6c8;padding:40px 24px;">
  <div style="max-width:480px;margin:0 auto;">
    <h2 style="color:#ffb800;">Your trial expires in {days_left} days</h2>
    <p style="color:#9a8a6a;">After that, Frida detection, MITM, AI monitoring, RASP will stop working. Your app will fall back to Free tier.</p>
    <p style="color:#9a8a6a;">Upgrade now to keep all 25 security modules active.</p>
    <a href="https://tejasai.io/security#pricing" style="display:inline-block;background:#ffb800;color:#04080f;font-size:13px;font-weight:700;padding:12px 24px;border-radius:6px;text-decoration:none;margin-top:16px;">Upgrade to Pro — ₹3,999/mo</a>
    <p style="font-size:11px;color:#4a4030;margin-top:24px;">TejasAI · support@tejasai.io</p>
  </div>
</body>
</html>
""",
        })
        return True
    except Exception as e:
        print(f"Expiry warning email failed: {e}")
        return False
