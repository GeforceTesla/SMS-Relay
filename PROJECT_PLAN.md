Private Encrypted SMS Relay — Full Implementation Plan
1. Goal

Build a private Android-to-server SMS relay.

Android phone receives SMS
  -> app stores SMS in local queue
  -> app encrypts SMS payload
  -> app POSTs encrypted payload to public HTTPS endpoint
  -> server authenticates request
  -> server decrypts payload
  -> server stores SMS in SQLite
  -> web UI displays messages

Requirements:

- No always-on VPN required
- Public HTTPS endpoint allowed
- Application-level encryption required in v1
- SMS body must not be visible on wire
- Server runs inside isolated container
- Android should survive background restrictions
- Private sideload app, not Play Store target
2. Architecture
[Android SMS Relay App]
  - RECEIVE_SMS BroadcastReceiver
  - Room local queue
  - WorkManager uploader
  - AES-GCM + RSA-OAEP encryption
  - OkHttp HTTPS client

        |
        | HTTPS POST encrypted JSON
        v

[Reverse Proxy]
  - Caddy or Nginx
  - TLS certificate
  - rate limiting if Nginx/Caddy plugin available
  - forwards only /api/v1/sms and web UI routes

        |
        v

[SMS Server Container]
  - FastAPI
  - SQLite
  - RSA private key
  - bearer token auth
  - decrypts payload
  - stores plaintext locally
  - simple web UI
3. Repository Structure
sms-relay/
  server/
    app/
      main.py
      config.py
      db.py
      crypto.py
      models.py
      auth.py
      templates/
        index.html
        message.html
      static/
        style.css
    tests/
      test_crypto.py
      test_api.py
      test_replay.py
      test_logging.py
    Dockerfile
    docker-compose.yml
    requirements.txt
    generate_keys.py
    .env.example

  android/
    app/
      build.gradle.kts
      src/main/
        AndroidManifest.xml
        java/com/example/smsrelay/
          MainActivity.kt
          SmsReceiver.kt
          SmsUploadWorker.kt
          SmsRepository.kt
          SmsDatabase.kt
          OutboundSmsEntity.kt
          Crypto.kt
          ApiClient.kt
          SettingsStore.kt
          BootReceiver.kt
          PermissionHelper.kt

  docs/
    DEPLOY.md
    SECURITY.md
    ANDROID_SETUP.md
    THREAT_MODEL.md
4. Crypto Design

Use hybrid encryption.

Phone side

For each SMS:

1. Create plaintext SMS JSON.
2. Generate random 256-bit AES key.
3. Generate random 12-byte AES-GCM nonce.
4. Encrypt plaintext JSON using AES-256-GCM.
5. Encrypt AES key using server RSA public key.
6. POST encrypted payload to server.
Server side
1. Verify bearer token.
2. Decode encrypted payload.
3. Decrypt AES key using RSA private key.
4. Decrypt ciphertext using AES-GCM.
5. Validate plaintext schema.
6. Store SMS in SQLite.
Algorithms
Payload encryption: AES-256-GCM
Key encryption: RSA-OAEP with SHA-256
Transport: HTTPS
Auth: Bearer token
Replay protection: client_id + message_id unique constraint
5. Wire Payload

The server only accepts this encrypted envelope:

{
  "version": 1,
  "client_id": "phone-1",
  "message_id": "f71fcb9d-f9b2-49b5-9e1b-5b79c2a78e33",
  "encrypted_key": "base64",
  "nonce": "base64",
  "ciphertext": "base64",
  "created_at": 1710000000000
}

Inner plaintext before encryption:

{
  "sender": "+15551234567",
  "body": "hello",
  "received_at_phone": 1710000000000,
  "sim_slot": 1
}

Never send plaintext SMS body in the outer payload.

6. Server Implementation
Stack
Python 3.12
FastAPI
Uvicorn
SQLite
Jinja2 templates
cryptography
Docker Compose
Endpoints
POST /api/v1/sms
GET  /
GET  /messages/{id}
GET  /healthz

Optional admin/API later:

GET /api/v1/messages
DELETE /api/v1/messages/{id}
FastAPI config

Disable docs in production:

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
Server database schema
CREATE TABLE sms_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  client_message_id TEXT NOT NULL,
  sender TEXT NOT NULL,
  body TEXT NOT NULL,
  received_at_phone INTEGER NOT NULL,
  received_at_server INTEGER NOT NULL,
  sim_slot INTEGER,
  raw_json TEXT NOT NULL,
  UNIQUE(client_id, client_message_id)
);

CREATE INDEX idx_sms_received_at_server
ON sms_messages(received_at_server);

CREATE INDEX idx_sms_sender
ON sms_messages(sender);
Server config

Environment variables:

SMS_RELAY_BEARER_TOKEN=long-random-token
SMS_RELAY_DB_PATH=/app/data/sms.db
SMS_RELAY_PRIVATE_KEY_PATH=/app/keys/server_private.pem
SMS_RELAY_MAX_BODY_BYTES=65536
SMS_RELAY_ALLOWED_CLIENT_IDS=phone-1
Server behavior

POST /api/v1/sms:

1. Check Authorization header.
2. Validate JSON envelope.
3. Check version == 1.
4. Check client_id is allowed.
5. Check payload size limit.
6. Base64-decode encrypted_key, nonce, ciphertext.
7. RSA-OAEP decrypt AES key.
8. AES-GCM decrypt ciphertext.
9. Parse inner SMS JSON.
10. Validate fields.
11. Insert into SQLite.
12. If duplicate client_id + message_id, return 200 idempotently.
13. Return {"status":"ok"}.

Important logging rule:

Do not log:
- SMS body
- decrypted plaintext JSON
- encrypted payload
- bearer token

Allowed logs:

client_id, message_id, sender hash, success/failure reason
7. Server Container Isolation

Use Docker Compose.

Container hardening:

services:
  sms-api:
    build: .
    restart: unless-stopped
    read_only: true
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    tmpfs:
      - /tmp
    volumes:
      - ./data:/app/data
      - ./keys:/app/keys:ro
    environment:
      - SMS_RELAY_DB_PATH=/app/data/sms.db
      - SMS_RELAY_PRIVATE_KEY_PATH=/app/keys/server_private.pem
    networks:
      - sms_net

Do not mount:

- Docker socket
- NFS shares
- SMB shares
- host /
- SSH keys
- personal files

Network design:

Internet
  -> reverse proxy
  -> sms-api container only

The SMS container should not be able to reach your NAS services if possible.

8. Reverse Proxy

Use Caddy if you want easiest TLS:

sms.yourdomain.com {
  reverse_proxy sms-api:8000
}

Better hardening:

- Only expose HTTPS 443
- Redirect HTTP to HTTPS
- Limit body size
- Rate limit /api/v1/sms if available
- Do not expose FastAPI docs

If using Nginx:

client_max_body_size 128k;
limit_req zone=sms burst=10 nodelay;
9. Android Implementation
Stack
Kotlin
AndroidX
Room
WorkManager
OkHttp
Jetpack Compose or simple XML UI
Android permissions
<uses-permission android:name="android.permission.RECEIVE_SMS" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

Runtime permission:

RECEIVE_SMS

This is intended for sideload/private install. Do not design for Play Store approval in v1.

10. Android Components
SmsReceiver.kt

Responsibilities:

- Receive SMS broadcast
- Extract sender/body/timestamp
- Generate client_message_id UUID
- Insert plaintext SMS into Room queue
- Enqueue SmsUploadWorker
- Return quickly

Do not do network upload directly inside receiver.

Room queue

Table:

CREATE TABLE outbound_sms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_message_id TEXT UNIQUE NOT NULL,
  sender TEXT NOT NULL,
  body TEXT NOT NULL,
  received_at_phone INTEGER NOT NULL,
  sim_slot INTEGER,
  status TEXT NOT NULL,
  retry_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at INTEGER NOT NULL,
  uploaded_at INTEGER
);

Statuses:

pending
uploading
uploaded
failed
SmsUploadWorker.kt

Responsibilities:

1. Load pending messages.
2. Encrypt each message.
3. POST encrypted envelope to server.
4. On HTTP 200, mark uploaded.
5. On temporary failure, retry.
6. On permanent crypto/config error, mark failed.

Use:

NetworkType.CONNECTED
Exponential backoff
Unique work name: sms-upload
ApiClient.kt

Responsibilities:

- OkHttp client
- Adds Authorization bearer token
- POST /api/v1/sms
- Timeout handling
- No logging interceptor that logs bodies
Crypto.kt

Responsibilities:

- Load server public key
- Generate AES-256 key
- Generate 12-byte nonce
- AES-GCM encrypt plaintext JSON
- RSA-OAEP SHA-256 encrypt AES key
- Base64 encode envelope fields
SettingsStore.kt

Store:

server_url
bearer_token
client_id
server_public_key_pem

For v1, allow manual paste/import of public key.

Better security later:

Hardcode expected public key fingerprint.
MainActivity.kt

Simple UI:

- Permission status
- Server URL
- Client ID
- Bearer token field
- Public key import field
- Queue length
- Last upload status
- Send test encrypted message button
- Open battery optimization settings button
11. Android Reliability Rules

Do:

- Use BroadcastReceiver only to capture SMS and queue.
- Use WorkManager for upload.
- Store before uploading.
- Mark uploaded only after server confirms.
- Retry on network/server failures.
- Show queue length in UI.

Do not:

- Use a forever background service.
- Upload directly inside BroadcastReceiver.
- Keep SMS only in RAM.
- Log SMS body.

Expected behavior:

Normal screen off: should work.
No network: queues locally.
Battery saver: upload may be delayed.
Force-stopped app: receiver may not run until app is opened again.
Aggressive OEM battery policy: user may need Unrestricted battery mode.
12. Security Requirements
Required in v1
- HTTPS
- Bearer token auth
- App-level encryption
- RSA private key only on server
- Server public key on phone
- AES-GCM fresh key per message
- Fresh nonce per message
- Replay protection
- Container isolation
- No plaintext logs
- FastAPI docs disabled
Not required in v1
- Ed25519 client signatures
- Encrypted-at-rest Android queue
- Encrypted SQLite server DB
- Multi-user admin accounts
- Browser-side decryption
Good v2 upgrades
- Ed25519 client signing
- Android encrypted Room DB
- Server SQLite encryption or disk encryption
- Web login
- 2FA for web UI
- Per-client token rotation
- Message deletion/audit log
13. Testing Plan
Server tests
test_valid_encrypted_payload_is_accepted
test_wrong_bearer_token_rejected
test_missing_bearer_token_rejected
test_duplicate_message_id_is_idempotent
test_tampered_ciphertext_rejected
test_tampered_encrypted_key_rejected
test_wrong_client_id_rejected
test_payload_too_large_rejected
test_plaintext_payload_rejected
test_sms_body_not_in_logs
Android tests
test_crypto_encrypts_payload_server_can_decrypt
test_receiver_inserts_sms_into_queue
test_worker_marks_uploaded_on_200
test_worker_retries_on_network_failure
test_worker_does_not_delete_on_failure
test_no_body_logging
Manual tests
1. Install APK.
2. Grant SMS permission.
3. Send test SMS to phone.
4. Confirm queue gets message.
5. Confirm server receives encrypted payload.
6. Confirm web UI displays message.
7. Disable network, send SMS, confirm queued.
8. Re-enable network, confirm upload.
9. Restart phone, confirm app still works.
14. Milestones
Milestone 1 — Server encrypted API

Deliver:

- FastAPI app
- SQLite schema
- RSA key loader
- AES-GCM/RSA-OAEP decrypt
- Bearer token auth
- Replay protection
- Basic web UI
- Dockerfile
- docker-compose.yml
- Tests
Milestone 2 — Android encrypted client

Deliver:

- Kotlin app
- SMS receiver
- Room queue
- WorkManager uploader
- AES-GCM/RSA-OAEP encrypt
- OkHttp POST
- Settings UI
- Test message button
Milestone 3 — Deployment

Deliver:

- Reverse proxy config
- TLS setup
- Container hardening
- .env.example
- Key generation docs
- Backup docs
Milestone 4 — Reliability polish

Deliver:

- Battery optimization helper
- Better retry visibility
- Queue inspector
- Manual resend
- Error diagnostics
Milestone 5 — Security polish

Deliver:

- Ed25519 client signature
- Optional encrypted Android queue
- Web UI login
- Rate limiting
- Alert on repeated failed auth
15. Codex Prompt

Use this as the initial Codex prompt:

Build a private encrypted SMS relay system with two components:

1. server/: Python FastAPI app running in Docker.
2. android/: Kotlin Android app.

Core requirements:
- Android receives incoming SMS and forwards them to the server.
- The phone must not require always-on VPN.
- The server is exposed via public HTTPS endpoint.
- Application-level encryption is required in v1.
- No plaintext SMS body may be sent over the wire.
- The server runs in an isolated Docker container.
- This is for private sideload use, not Google Play distribution.

Server requirements:
- Use Python 3.12, FastAPI, SQLite, cryptography, Jinja2.
- Disable FastAPI docs/redoc/openapi in production.
- Implement POST /api/v1/sms.
- Implement GET / and GET /messages/{id} for simple web UI.
- Implement GET /healthz.
- Require Authorization: Bearer <token>.
- Accept encrypted payload only.
- Payload format:
  {
    "version": 1,
    "client_id": "phone-1",
    "message_id": "uuid",
    "encrypted_key": "base64",
    "nonce": "base64",
    "ciphertext": "base64",
    "created_at": 1710000000000
  }
- Decrypt encrypted_key using RSA-OAEP with SHA-256 and server private key.
- Decrypt ciphertext using AES-256-GCM.
- Inner plaintext JSON format:
  {
    "sender": "+15551234567",
    "body": "hello",
    "received_at_phone": 1710000000000,
    "sim_slot": 1
  }
- Store decrypted SMS in SQLite.
- Add unique constraint on client_id + message_id for replay protection.
- Treat duplicate client_id + message_id as idempotent success.
- Never log plaintext SMS body, bearer token, or decrypted JSON.
- Include Dockerfile and docker-compose.yml.
- Store SQLite in /app/data.
- Load private key from /app/keys/server_private.pem.
- Provide generate_keys.py to create RSA keypair.
- Provide .env.example.
- Add pytest tests for valid payload, wrong token, duplicate message, tampered ciphertext, tampered encrypted key, plaintext rejection, and no SMS body in logs.

Android requirements:
- Use Kotlin.
- Use RECEIVE_SMS permission.
- Use BroadcastReceiver for incoming SMS.
- Use Room database as local outbound queue.
- Use WorkManager for uploads.
- Use OkHttp for HTTPS POST.
- Do not use a long-running background service.
- SmsReceiver must only parse SMS, store to Room, and enqueue worker.
- WorkManager must encrypt and upload pending messages.
- Mark messages uploaded only after HTTP 200.
- Retry on network/server failure with exponential backoff.
- Generate a UUID message_id per SMS.
- Use client_id from settings.
- Use AES-256-GCM with fresh random 256-bit AES key per message.
- Use fresh random 12-byte GCM nonce per message.
- Encrypt AES key using server RSA public key with RSA-OAEP SHA-256.
- Build encrypted envelope exactly matching the server format.
- Settings screen should include server URL, bearer token, client_id, server public key PEM, queue length, last upload status, and send test encrypted message button.
- Do not log SMS body or encrypted payload.
- Local Room queue may store plaintext for v1, but keep storage behind repository abstraction so encrypted-at-rest can be added later.

Deployment requirements:
- Provide docs/DEPLOY.md.
- Provide docs/SECURITY.md.
- Provide docs/ANDROID_SETUP.md.
- Explain reverse proxy setup with Caddy or Nginx.
- Explain battery optimization caveats on Android.
- Explain that if the app is force-stopped, Android may not deliver SMS broadcasts until the app is opened again.

Implement Milestone 1 server first, then Milestone 2 Android client.