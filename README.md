# Private Encrypted SMS Relay

Private Android-to-server SMS relay with application-level encryption.

The Android app receives SMS, stores them in a local queue, encrypts each message, and uploads only an encrypted envelope to the server. The server decrypts and stores messages in SQLite. The web UI reads messages from SQLite.

## Current Architecture

There are two server entrypoints:

```text
public_app   -> receiver API only
private_app  -> web UI / message reader only
```

Recommended ports:

```text
0.0.0.0:8000  public SMS receiver
0.0.0.0:8001  private web UI
```

Expose/port-forward only `8000` publicly. Keep `8001` reachable only through LAN, VPN, firewall allowlist, or SSH tunnel.

Android app should use HTTPS in production:

```text
https://sms.example.com
```

For local development only, older debug builds could use `http://<server-ip>:8000`; the current Android app expects HTTPS for normal use.

Web UI uses the private/internal port:

```text
http://<server-ip-or-domain>:8001
```

## Server Setup

From the repo root:

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Generate RSA keys once:

```bash
python generate_keys.py --output-dir keys
```

This creates:

```text
server/keys/server_private.pem
server/keys/server_public.pem
```

Paste the full public key into the Android app, including:

```text
-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----
```

Create the data directory and config file:

```bash
mkdir -p data
cp config.example.toml config.toml
```

Edit `config.toml`:

```toml
[server]
bearer_token = "replace-with-a-long-random-token"
db_path = "./data/sms.db"
private_key_path = "./keys/server_private.pem"
max_body_bytes = 65536
allowed_client_ids = ["phone-1", "phone-2"]
```

## SQLite Database Location

The SQLite database path is configurable in `server/config.toml`:

```toml
[server]
db_path = "./data/sms.db"
```

For manual/local runs, relative paths are resolved from the `server/` directory when you start the server there. The default local database location is therefore:

```text
server/data/sms.db
```

You can move it anywhere the server process can read/write, for example:

```toml
db_path = "/home/geforceiridium/sms-relay-data/sms.db"
```

For Docker, use the container path:

```toml
db_path = "/app/data/sms.db"
```

That maps to this host path through Docker Compose:

```text
server/data/sms.db
```

If you change the Docker database path outside `/app/data`, update `server/docker-compose.yml` volumes too.

## Run Server With Scripts

After creating `.venv` and `config.toml`, you can start the server with helper scripts.

Run both receiver and web UI in one terminal:

```bash
cd /home/geforceiridium/sms-relay/server
./scripts/run-dev.sh
```

Run only the public receiver:

```bash
cd /home/geforceiridium/sms-relay/server
./scripts/run-receiver.sh
```

Run only the private web UI:

```bash
cd /home/geforceiridium/sms-relay/server
./scripts/run-web.sh
```

Default bindings:

```text
receiver: 0.0.0.0:8000
web UI:   0.0.0.0:8001
```

Override host/port if needed:

```bash
SMS_RELAY_RECEIVER_PORT=9000 ./scripts/run-receiver.sh
SMS_RELAY_WEB_HOST=127.0.0.1 SMS_RELAY_WEB_PORT=9001 ./scripts/run-web.sh
```

## Run Server Manually

The server reads settings from `config.toml` in the `server/` directory.

Terminal 1: public receiver API:

```bash
cd /home/geforceiridium/sms-relay/server
. .venv/bin/activate
uvicorn app.main:public_app --host 0.0.0.0 --port 8000
```

Terminal 2: private web UI:

```bash
cd /home/geforceiridium/sms-relay/server
. .venv/bin/activate
uvicorn app.main:private_app --host 0.0.0.0 --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8001/healthz
```

Expected:

```json
{"status":"ok"}
```

## Android Build

Requirements:

- Java 17
- Gradle
- Android SDK with platform/build tools for API 35

If needed, set `local.properties` in the repo root:

```text
sdk.dir=/home/geforceiridium/android-sdk
```

Build debug APK:

```bash
cd /home/geforceiridium/sms-relay
gradle :android:app:assembleDebug
```

APK path:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

Install with ADB:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

Or copy the APK to the phone and sideload it.

## Android App Configuration

Open the app, then open the three-dot menu -> Settings.

Set:

```text
Server URL: https://sms.example.com
Bearer token: dev-token-change-me
Client ID: phone-1
Server public key PEM: contents of server/keys/server_public.pem
```

Client ID identifies which phone received the message. If using multiple phones, set different IDs such as:

```text
phone-1
phone-2
work-phone
```

The server must allow those IDs in `server/config.toml`:

```toml
allowed_client_ids = ["phone-1", "phone-2", "work-phone"]
```

Settings are stored in Android SharedPreferences and survive normal APK updates. They are removed if you uninstall the app or clear app data.

## Testing

### Test Encrypted Upload Without Real SMS

In the Android app main screen:

1. Enter custom text in **Test Message**.
2. Tap **Send Test Message**.
3. Watch **Last upload** status.
4. Open the web UI:

```text
http://<server-ip>:8001
```

Expected server web UI result:

- Sender thread for `+15550000000`
- Message body matching your custom test text

### Test Real Incoming SMS

1. In app Settings, tap **Grant SMS Permission**.
2. Confirm main screen shows:

```text
SMS permission: granted
```

3. Send an SMS to the phone from another phone or SMS service.
4. Open the web UI on port `8001`.
5. Click the sender to view history.

A same-phone self-SMS may not reliably trigger Android's incoming SMS broadcast path. Use another sender for a real test.

### Retry Queued Messages

If queue length grows and nothing appears in the web UI:

1. Confirm phone can open:

```text
https://sms.example.com/healthz
```

2. Confirm token/client ID/public key are correct.
3. Tap **Retry Upload Queue**.
4. Check server logs for:

```text
POST /api/v1/sms
```

## Web UI

Private web UI is on port `8001`.

Features:

- Groups messages by sender
- Shows newest message preview
- Shows receiver `client_id`
- Shows all receiver IDs per sender thread
- Sender history newest-first
- Delete entire sender message chain
- Auto-refreshes when new messages arrive or messages are deleted
- Shows server-local received time

## Run With Docker Compose

Docker Compose is the recommended deployment path because it runs the receiver and web UI in hardened containers instead of plain host Uvicorn processes.

The compose file runs two containers from the same image:

```text
sms-receiver -> app.main:public_app  -> 8000
sms-web      -> app.main:private_app -> 8001
```

The receiver container exposes only the encrypted SMS upload API. The web container exposes only the private reader UI.

### 1. Prepare Server Files

From the repo root:

```bash
cd /home/geforceiridium/sms-relay/server
mkdir -p data keys
```

Generate RSA keys once if they do not already exist:

```bash
python3 generate_keys.py --output-dir keys
```

This creates:

```text
keys/server_private.pem
keys/server_public.pem
```

The Android app needs the full contents of `keys/server_public.pem`.

### 2. Create `config.toml`

```bash
cp config.example.toml config.toml
```

Edit `config.toml` for Docker paths:

```toml
[server]
bearer_token = "replace-with-a-long-random-token"
db_path = "/app/data/sms.db"
private_key_path = "/app/keys/server_private.pem"
max_body_bytes = 65536
allowed_client_ids = ["phone-1", "phone-2"]
```

Use the same bearer token in the Android app.

### 3. Start Containers

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs -f
```

Or for one service:

```bash
docker compose logs -f sms-receiver
docker compose logs -f sms-web
```

### 4. Verify Ports

Receiver health:

```bash
curl http://127.0.0.1:8000/healthz
```

Web UI health:

```bash
curl http://127.0.0.1:8001/healthz
```

Expected:

```json
{"status":"ok"}
```

Open the web UI:

```text
http://<server-ip>:8001
```

Configure Android server URL as:

```text
https://sms.example.com
```

### 5. Port Exposure Plan

Compose publishes both ports on the host:

```text
8000:8000  public SMS receiver
8001:8001  private web UI
```

Only port-forward or reverse-proxy `8000` publicly. Leave `8001` unforwarded and reachable only by LAN/VPN/firewall rules.

### 6. Stop Or Restart

Stop:

```bash
docker compose down
```

Restart after config changes:

```bash
docker compose up -d
```

Rebuild after code changes:

```bash
docker compose up -d --build
```

### 7. Container Isolation Notes

Both containers use:

```yaml
read_only: true
cap_drop:
  - ALL
security_opt:
  - no-new-privileges:true
tmpfs:
  - /tmp
```

Mounted data:

```text
sms-receiver: ./data:/app/data, ./keys:/app/keys:ro
sms-web:      ./data:/app/data
```

The web UI container does not mount the RSA private key. It can still read/write SQLite because it displays and deletes stored messages.

## Cloudflare DDNS

Use this when your home public IP can change. The updater keeps a Cloudflare DNS record, such as `sms.example.com`, pointed at your current public IP.

Recommended order:

1. Configure and test DDNS for the `sms.example.com` A record.
2. Start Caddy/HTTPS.
3. Forward router ports `80` and `443` last.

The updater creates the DNS record if it does not already exist.

### 1. Create A Cloudflare API Token

Create a Cloudflare API token scoped to this one zone with:

```text
Zone:DNS:Edit
Zone:Zone:Read
```

### 2. Configure DDNS

```bash
cd /home/geforceiridium/sms-relay/server
cp ddns.env.example ddns.env
nano ddns.env
```

Set:

```bash
CF_API_TOKEN="your-cloudflare-token"
CF_ZONE_NAME="example.com"
CF_RECORD_NAME="sms.example.com"
CF_RECORD_TYPE="A"
CF_RECORD_PROXIED="true"
CF_RECORD_TTL="1"
```

`ddns.env` is ignored by git and Docker. Do not commit it.

### 3. Test One Update

```bash
cd /home/geforceiridium/sms-relay/server
./scripts/cloudflare-ddns.sh
```

Expected output is one of:

```text
Cloudflare DDNS created: sms.example.com -> <public-ip> proxied=true
Cloudflare DDNS unchanged: sms.example.com -> <public-ip> proxied=true
Cloudflare DDNS updated: sms.example.com <old-ip> -> <public-ip> proxied=true
```

### 4. Run DDNS On A Timer

Install the included systemd timer:

```bash
cd /home/geforceiridium/sms-relay/server
sudo cp systemd/sms-relay-ddns.service /etc/systemd/system/
sudo cp systemd/sms-relay-ddns.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sms-relay-ddns.timer
```

Check it:

```bash
systemctl list-timers sms-relay-ddns.timer
sudo systemctl status sms-relay-ddns.service
sudo journalctl -u sms-relay-ddns.service -n 50 --no-pager
```

Run an immediate manual update any time:

```bash
sudo systemctl start sms-relay-ddns.service
```

### 5. Router Forwarding Comes Last

After DDNS is working and Caddy is configured, forward only:

```text
80  -> NAS/server port 80
443 -> NAS/server port 443
```

Do not forward `8001`. The private web UI should stay LAN/VPN-only.

## HTTPS Reverse Proxy Deployment

Public HTTPS should forward only the receiver endpoint. The included Caddy example does this and returns `404` for everything else.

Conceptual routing:

```text
Internet
  -> https://sms.example.com/api/v1/sms
  -> Caddy
  -> sms-receiver:8000/api/v1/sms
```

The private web UI on `8001` is not proxied publicly.

### Caddy Setup

Create DNS for your domain so it points to this server, for example:

```text
sms.example.com -> your public IP
```

Copy and edit the Caddyfile:

```bash
cd /home/geforceiridium/sms-relay/server
cp Caddyfile.example Caddyfile
# edit Caddyfile and replace sms.example.com with your real domain
```

Start app containers plus Caddy:

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

Caddy listens on public ports `80` and `443`, gets/renews certificates automatically, and proxies only:

```text
/api/v1/sms
/healthz
```

Configure the Android app server URL as:

```text
https://sms.example.com
```

Do not publicly proxy the web UI.

Access web UI through one of:

- VPN
- LAN-only IP
- firewall allowlist
- SSH tunnel

Example SSH tunnel:

```bash
ssh -L 8001:127.0.0.1:8001 user@server
```

Then open locally:

```text
http://127.0.0.1:8001
```

## Start On Boot

Docker is configured with `restart: unless-stopped` for the SMS receiver, private web UI, and Caddy containers. If Docker starts on boot, previously created containers should restart automatically.

Check Docker boot status:

```bash
systemctl is-enabled docker
systemctl is-active docker
```

Enable Docker if needed:

```bash
sudo systemctl enable --now docker
```

For an explicit SMS Relay startup service, install the included systemd unit:

```bash
cd /home/geforceiridium/sms-relay/server
sudo cp systemd/sms-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sms-relay.service
```

Check status:

```bash
systemctl status sms-relay.service
docker compose -f docker-compose.yml -f docker-compose.https.yml ps
```

The Cloudflare DDNS timer should also be enabled:

```bash
systemctl list-timers sms-relay-ddns.timer
```

Stop the Docker stack intentionally:

```bash
sudo systemctl stop sms-relay.service
```

Start it again:

```bash
sudo systemctl start sms-relay.service
```

## Security Notes

- SMS body is encrypted on the phone before upload.
- Outer wire payload does not include plaintext SMS body.
- Server decrypts and stores plaintext in SQLite.
- Bearer token is required for receiver API.
- Replay protection uses unique `(client_id, message_id)`.
- FastAPI docs/openapi/redoc are disabled.
- Server logs avoid SMS body, bearer token, decrypted JSON, and encrypted payload.
- Android local queue stores plaintext for v1.
- Server SQLite is plaintext for v1.
- Android cleartext HTTP is disabled; use HTTPS for the receiver URL.

For production:

- Use HTTPS for port `8000` via reverse proxy.
- Use a long random bearer token.
- Restrict `8001` to VPN/internal access.
- Consider disk encryption or encrypted SQLite.
- Consider Android encrypted Room DB.
- Consider client signatures and token rotation.
