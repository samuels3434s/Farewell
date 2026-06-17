import os
import json
import time
import io
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, redirect, session
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# Session config for OAuth state validation
app.secret_key = os.getenv('SECRET_KEY', 'event-camera-secret-key-123456')

PORT = int(os.getenv('PORT', 3000))
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID')
STATUS_FILE = 'upload_status.json'
TOKEN_FILE = 'token.json'
CLIENT_SECRETS_FILE = 'client_secrets.json'

# Google Drive Client variables
drive_service = None
is_mock_mode = False
is_authorized = False

# Helper to read/write persistent upload status
def get_upload_status():
    if not os.path.exists(STATUS_FILE):
        set_upload_status(True)
        return True
    try:
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('uploads_enabled', True)
    except Exception as e:
        print(f"Error reading status file: {e}")
        return True

def set_upload_status(enabled):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump({'uploads_enabled': enabled, 'updated_at': str(datetime.now())}, f)
        return True
    except Exception as e:
        print(f"Error writing status file: {e}")
        return False

# Initialize Google Drive client (OAuth 2.0)
def initialize_google_drive():
    global drive_service, is_mock_mode, is_authorized
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        creds = None
        
        # 1. Check if token.json exists (already authorized)
        if os.path.exists(TOKEN_FILE):
            print(f"Loading credentials from {TOKEN_FILE}...", flush=True)
            creds = Credentials.from_authorized_user_file(
                TOKEN_FILE, 
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            # If credentials are expired, refresh them
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("OAuth credentials expired. Refreshing token...", flush=True)
                    creds.refresh(Request())
                    # Save refreshed token
                    with open(TOKEN_FILE, 'w') as f:
                        f.write(creds.to_json())
                    print("OAuth credentials successfully refreshed!", flush=True)
                except Exception as refresh_err:
                    print(f"Error refreshing expired credentials: {refresh_err}", flush=True)
                    creds = None # Force re-auth
        
        # 2. Build service if credentials are valid
        if creds and creds.valid:
            drive_service = build('drive', 'v3', credentials=creds)
            is_authorized = True
            is_mock_mode = False
            print("Google Drive client successfully authorized via OAuth 2.0!", flush=True)
        else:
            is_authorized = False
            # Check if client_secrets.json is present, if not fallback to Developer Mock Mode
            if os.path.exists(CLIENT_SECRETS_FILE):
                print(f"\x1b[33mWarning: Server is NOT authorized. Visit http://localhost:{PORT}/admin to authorize your Google Drive.\x1b[0m", flush=True)
                is_mock_mode = False
                drive_service = None
            else:
                trigger_mock_mode("No token.json or client_secrets.json found.")
            
    except Exception as e:
        print(f"Error setting up Google Drive API: {e}", flush=True)
        trigger_mock_mode(str(e))

    if not is_mock_mode and (not DRIVE_FOLDER_ID or DRIVE_FOLDER_ID == 'your_google_drive_folder_id_here'):
        print("\x1b[33mWarning: DRIVE_FOLDER_ID is missing or set to placeholder.\x1b[0m", flush=True)

def trigger_mock_mode(reason):
    global is_mock_mode, drive_service, is_authorized
    is_mock_mode = True
    is_authorized = False
    drive_service = None
    print(f"\x1b[36mRunning in DEVELOPER MOCK MODE: {reason}\x1b[0m", flush=True)
    print("\x1b[36mUploads will simulate successful saves without hitting Google APIs.\x1b[0m", flush=True)

# Initialize on startup
initialize_google_drive()

# Serve index.html at root
@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')

# Serve admin.html
@app.route('/admin')
def serve_admin_shortcut():
    return send_from_directory('public', 'admin.html')

# Endpoint: GET Status (Open to public)
@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'uploads_enabled': get_upload_status(),
        'is_mock_mode': is_mock_mode,
        'is_authorized': is_authorized,
        'folder_configured': bool(DRIVE_FOLDER_ID and DRIVE_FOLDER_ID != 'your_google_drive_folder_id_here'),
        'client_secrets_present': os.path.exists(CLIENT_SECRETS_FILE)
    })

# Endpoint: POST Toggle Uploads (Requires Admin Password)
@app.route('/api/admin/toggle', methods=['POST'])
def api_admin_toggle():
    data = request.json or {}
    password = data.get('password')
    enabled = data.get('enabled')

    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'error': 'Invalid admin password'}), 401
    
    if enabled is None:
        return jsonify({'success': False, 'error': 'Missing "enabled" boolean parameter'}), 400

    success = set_upload_status(enabled)
    if success:
        return jsonify({
            'success': True,
            'uploads_enabled': enabled,
            'message': f"Uploads {'enabled' if enabled else 'disabled'} successfully."
        })
    else:
        return jsonify({'success': False, 'error': 'Failed to save status on server'}), 500


# ==========================================
# Google OAuth 2.0 Authorization Endpoints
# ==========================================

@app.route('/api/auth/login')
def api_auth_login():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return jsonify({
            'success': False,
            'error': f"File '{CLIENT_SECRETS_FILE}' is missing from the root directory. Please generate and place it first."
        }), 400
        
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Dynamically determine redirect URI based on host header (supports Render & ngrok proxy HTTPS)
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        redirect_uri = f"{scheme}://{request.host}/api/auth/callback"
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/drive'],
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent' # Forces Google to return a refresh token
        )
        
        session['oauth_state'] = state
        return redirect(authorization_url)
        
    except Exception as e:
        print(f"Error starting OAuth flow: {e}", flush=True)
        return f"Failed to start Google OAuth flow: {str(e)}", 500

@app.route('/api/auth/callback')
def api_auth_callback():
    state = session.get('oauth_state')
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        redirect_uri = f"{scheme}://{request.host}/api/auth/callback"
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/drive'],
            redirect_uri=redirect_uri,
            state=state
        )
        
        # Override insecure transport requirement in development/local HTTP mode
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        # Save credentials (with refresh token) to token.json
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
            
        print("Received OAuth callback! Credentials saved successfully.", flush=True)
        
        # Re-initialize Drive service
        initialize_google_drive()
        
        # Redirect back to admin console
        return redirect('/admin')
        
    except Exception as e:
        print(f"Error during OAuth callback: {e}", flush=True)
        return f"Authorization failed: {str(e)}", 500


# ==========================================
# File Upload Endpoint
# ==========================================

@app.route('/api/upload', methods=['POST'])
def api_upload():
    try:
        # Check if uploads are disabled
        if not get_upload_status():
            return jsonify({
                'success': False,
                'error': 'Uploads are currently closed by the event host.'
            }), 400

        # Validate file
        if 'photo' not in request.files:
            return jsonify({'success': False, 'error': 'No photo file in multipart request.'}), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename.'}), 400

        # Format filename: Farewell_YYYYMMDD_HHMMSS.jpg
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            ext = '.jpg'
        filename = f"Farewell_{timestamp}{ext}"

        file_data = file.read()
        file_size_mb = len(file_data) / (1024 * 1024)
        print(f"Upload request. Size: {file_size_mb:.2f} MB, Target name: {filename}", flush=True)

        # Developer Mock Mode response
        if is_mock_mode:
            time.sleep(0.8 + (time.time() % 0.7))
            mock_id = f"mock_file_id_{int(time.time())}"
            print(f"[Mock Mode] Simulated upload for file: {filename} (ID: {mock_id})", flush=True)
            return jsonify({
                'success': True,
                'message': 'Photo shared successfully (Simulated Upload)',
                'fileId': mock_id,
                'fileName': filename,
                'link': f"https://drive.google.com/open?id={mock_id}"
            })

        # Real Google Drive Upload
        if not is_authorized or not drive_service:
            return jsonify({
                'success': False,
                'error': 'Google Drive is not authorized by the host. Tell the host to link their Google account.'
            }), 401

        from googleapiclient.http import MediaIoBaseUpload
        
        # Build file metadata
        file_metadata = {
            'name': filename
        }
        if DRIVE_FOLDER_ID and DRIVE_FOLDER_ID != 'your_google_drive_folder_id_here':
            file_metadata['parents'] = [DRIVE_FOLDER_ID]

        # Construct media upload wrapper in memory
        fh = io.BytesIO(file_data)
        media = MediaIoBaseUpload(fh, mimetype=file.mimetype, resumable=True)

        # Execute drive API call
        drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        print(f"Uploaded successfully to Google Drive. ID: {drive_file.get('id')}, Name: {drive_file.get('name')}", flush=True)
        
        return jsonify({
            'success': True,
            'message': 'Photo Shared Successfully!',
            'fileId': drive_file.get('id'),
            'fileName': drive_file.get('name'),
            'link': drive_file.get('webViewLink')
        })

    except Exception as e:
        # Check if it's a Google API specific error
        error_msg = str(e)
        diagnostic = "Internal Server Error"
        
        try:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError):
                status_code = e.resp.status
                content = e.content.decode('utf-8')
                print(f"\n\x1b[31m================= GOOGLE DRIVE API UPLOAD ERROR =================\x1b[0m", flush=True)
                print(f"\x1b[31mStatus Code:\x1b[0m {status_code}", flush=True)
                print(f"\x1b[31mRaw Response:\x1b[0m {content}", flush=True)
                
                try:
                    err_json = json.loads(content)
                    google_message = err_json.get('error', {}).get('message', '')
                    print(f"\x1b[33mError Message:\x1b[0m {google_message}", flush=True)
                    
                    if status_code == 404:
                        diagnostic = "The DRIVE_FOLDER_ID specified in your .env file was not found. Please double-check the ID."
                    elif status_code == 403:
                        diagnostic = "Access Denied. Make sure you have authorized the server with the account that has permissions for this folder."
                    else:
                        diagnostic = google_message
                except Exception:
                    diagnostic = f"Google API HTTP {status_code}"
                
                print(f"\x1b[32mDiagnostic Suggestion:\x1b[0m {diagnostic}", flush=True)
                print(f"\x1b[31m=================================================================\x1b[0m\n", flush=True)
                error_msg = diagnostic
        except ImportError:
            pass
            
        print(f"Error processing upload: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': 'Server encountered an error during upload.',
            'details': error_msg
        }), 500

# Serve static files route fallback
@app.route('/<path:path>')
def serve_static_fallback(path):
    return send_from_directory('public', path)

if __name__ == '__main__':
    print("==================================================", flush=True)
    print(f" Event Camera Python Server running on http://localhost:{PORT}", flush=True)
    print(f" Mode: {'MOCK UPLOADS' if is_mock_mode else 'GOOGLE DRIVE UPLOADS'}", flush=True)
    print(f" Target Folder ID: {DRIVE_FOLDER_ID}", flush=True)
    print("==================================================", flush=True)
    app.run(host='0.0.0.0', port=PORT, debug=True)
