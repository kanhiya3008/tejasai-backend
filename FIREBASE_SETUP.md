# Firebase Setup Guide

## Step 1 — Create Firebase Project

1. Go to https://console.firebase.google.com
2. Click "Add project" → Name it "tejasai-licenses"
3. Disable Google Analytics (not needed)
4. Click "Create project"

## Step 2 — Enable Firestore

1. In Firebase Console → Build → Firestore Database
2. Click "Create database"
3. Select "Start in production mode"
4. Choose region: asia-south1 (Mumbai — closest to India)
5. Click "Enable"

## Step 3 — Get Service Account Credentials

1. Firebase Console → Project Settings (gear icon) → Service accounts
2. Click "Generate new private key"
3. Save the downloaded JSON file as `firebase-credentials.json`
4. Put it in your backend folder (DO NOT commit to Git)

## Step 4 — Firestore Security Rules

Go to Firestore → Rules and paste:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // licenses — only server can read/write (no client access)
    match /licenses/{doc} {
      allow read, write: if false;
    }

    // usage_logs — only server
    match /usage_logs/{doc} {
      allow read, write: if false;
    }

    // trials — only server
    match /trials/{doc} {
      allow read, write: if false;
    }

    // payments — only server
    match /payments/{doc} {
      allow read, write: if false;
    }
  }
}
```

Click Publish.

## Step 5 — Firestore Indexes

Go to Firestore → Indexes → Composite → Add index:

| Collection | Field 1 | Field 2 | Query scope |
|------------|---------|---------|-------------|
| licenses | key_hash (ASC) | status (ASC) | Collection |
| licenses | email (ASC) | created_at (DESC) | Collection |
| licenses | razorpay_subscription_id (ASC) | — | Collection |
| trials | email (ASC) | — | Collection |

## Firestore Data Structure

### Collection: licenses
```json
{
  "key_hash": "sha256 hash of the actual key",
  "key_prefix": "USK-A1B2",
  "email": "buyer@example.com",
  "name": "Rahul Sharma",
  "plan": "pro",
  "billing": "monthly",
  "status": "active",
  "bundle_ids": ["com.company.app1", "com.company.app2"],
  "app_limit": 3,
  "features": { "frida_detection": true, "rasp": true, ... },
  "created_at": "2025-01-01T00:00:00Z",
  "expires_at": "2025-02-01T00:00:00Z",
  "trial": false,
  "payment_id": "pay_xxxxx",
  "razorpay_subscription_id": "sub_xxxxx"
}
```

### Collection: usage_logs
```json
{
  "license_id": "firestore document id",
  "bundle_id": "com.company.app",
  "platform": "android",
  "plugin_version": "1.2.0",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Collection: trials
```json
{
  "email": "user@example.com",
  "license_id": "firestore document id",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### Collection: payments
```json
{
  "license_id": "firestore document id",
  "payment_id": "pay_xxxxx",
  "amount": 3999,
  "currency": "INR",
  "email": "buyer@example.com",
  "plan": "pro",
  "billing": "monthly",
  "timestamp": "2025-01-01T00:00:00Z"
}
```
