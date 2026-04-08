# TejasAI License API — Backend

FastAPI backend for license key generation, validation, and management.
Uses Firebase Firestore for storage, Razorpay for payments, Resend for emails.

## All API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/trial` | Start 14-day free trial |
| POST | `/validate-license` | Validate license from Flutter plugin |
| POST | `/webhook/razorpay` | Razorpay payment webhook |
| POST | `/license-status` | Check license status |
| POST | `/admin/create-license` | Manually create license (admin) |
| DELETE | `/admin/revoke-license` | Revoke a license (admin) |

Interactive docs at: `https://your-api.up.railway.app/docs`

## Local Setup

### 1. Clone and install
```bash
cd tejasai-backend
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. Firebase credentials
- Follow `FIREBASE_SETUP.md` to get your `firebase-credentials.json`
- Place it in this folder

### 3. Environment variables
```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Run locally
```bash
uvicorn main:app --reload
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Deploy to Railway

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial backend"
git remote add origin https://github.com/yourusername/tejasai-backend.git
git push -u origin main
```

### 2. Railway setup
1. Go to railway.app → New Project → Deploy from GitHub
2. Select your repo
3. Railway auto-detects Python + Procfile

### 3. Add environment variables in Railway dashboard

Go to your Railway project → Variables → Add all from `.env.example`:

| Variable | Where to get |
|----------|-------------|
| `FIREBASE_CREDENTIALS_JSON` | Paste entire firebase-credentials.json content |
| `RAZORPAY_KEY_ID` | Razorpay dashboard → Settings → API Keys |
| `RAZORPAY_KEY_SECRET` | Razorpay dashboard → Settings → API Keys |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay dashboard → Webhooks → Secret |
| `RESEND_API_KEY` | resend.com → API Keys |
| `FROM_EMAIL` | noreply@tejasai.io (after domain verified in Resend) |
| `APP_SECRET_KEY` | Any random 64-char string |
| `ALLOWED_ORIGINS` | https://tejasai.io,http://localhost:3000 |

### 4. Get your Railway URL
Railway gives you a URL like: `https://tejasai-backend.up.railway.app`

Update in Next.js `components/Trial.tsx`:
```ts
const res = await fetch('https://tejasai-backend.up.railway.app/trial', {
```

## Razorpay Webhook Setup

1. Razorpay Dashboard → Settings → Webhooks → Add new webhook
2. URL: `https://tejasai-backend.up.railway.app/webhook/razorpay`
3. Secret: same as `RAZORPAY_WEBHOOK_SECRET` in your .env
4. Events to enable:
   - `subscription.charged` ✓
   - `subscription.cancelled` ✓

## Testing Locally

### Test trial signup
```bash
curl -X POST http://localhost:8000/trial \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'
```

### Test license validation (from Flutter)
```bash
curl -X POST http://localhost:8000/validate-license \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "USK-XXXX-XXXX-XXXX",
    "bundle_id": "com.company.myapp",
    "platform": "android",
    "plugin_version": "1.2.0"
  }'
```

### Manually create enterprise license
```bash
curl -X POST http://localhost:8000/admin/create-license \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: YOUR_APP_SECRET_KEY" \
  -d '{
    "email": "enterprise@company.com",
    "plan": "enterprise",
    "billing": "annual",
    "name": "Company Name"
  }'
```

## Flutter Plugin Integration

In your plugin `initializeSecureMonitor()`:

```dart
Future<String> _validateLicense(String key) async {
  try {
    final response = await http.post(
      Uri.parse('https://tejasai-backend.up.railway.app/validate-license'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'license_key': key,
        'bundle_id': await _getBundleId(),
        'platform': Platform.operatingSystem,
        'plugin_version': '1.2.0',
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      _cacheValidation(key, data['plan']);   // offline cache
      return data['plan'];                  // free | trial | pro | enterprise
    }
    return 'free';
  } catch (e) {
    return _getCachedPlan(key) ?? 'free';  // offline grace period
  }
}
```
