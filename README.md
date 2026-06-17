# Event Camera Web App & Admin Console (OAuth 2.0)

A lightweight, mobile-responsive web app (and installable PWA) that opens a camera interface in the browser and uploads photos directly to a designated folder in your personal Google Drive account. Includes a password-protected **Admin Panel** to pause/activate uploads and authorize Google Drive access.

---

## Features

- **Frontend Camera**: Captures full-resolution uncompressed photo blobs (JPEG quality 1.0) and uploads them immediately in the background without blocking the camera screen.
- **Admin Control Panel**: Access `/admin` to toggle upload capabilities and link your personal Google Drive account. Toggling the upload switch instantly pauses the camera and displays a friendly notification on guests' screens.
- **OAuth 2.0 Web Flow**: Integrates with Google's OAuth 2.0 flow to link the server directly to your personal Drive account, bypassing the 0 GB storage quota limitations of Service Accounts.
- **PWA & Android WebView Wrapper**: Installable on home screens, and includes a native Android Studio template to compile into a native APK.

---

## 1. Google Cloud OAuth 2.0 Setup

To upload photos to your personal Google Drive, you need to create an OAuth Client ID:

### Step A: Configure OAuth Consent Screen
1. Go to the **[Google Cloud Console](https://console.cloud.google.com/)**.
2. Click the project dropdown in the top-left, click **New Project**, name it `Event Camera`, and click **Create**.
3. In the sidebar, navigate to **APIs & Services** > **Library**. Search for **Google Drive API** and click **Enable**.
4. Go to **APIs & Services** > **OAuth consent screen**.
5. Select **External** and click **Create**.
6. Fill in the required fields:
   - **App name**: `Event Camera`
   - **User support email**: (Your Gmail address)
   - **Developer contact information**: (Your Gmail address)
7. Click **Save and Continue**.
8. In the **Scopes** step, click **Add or Remove Scopes**, check the box for `.../auth/drive` (or `.../auth/drive.file`), and click **Save and Continue**.
9. In the **Test Users** step, click **+ Add Users** and type in **your target personal Google Drive email address**. (This is critical since the app is in Testing mode).
10. Click **Save and Continue**, review the summary, and click **Back to Dashboard**.

### Step B: Generate client_secrets.json
1. Navigate to **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** at the top and select **OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Under **Authorized redirect URIs**, click **+ Add URI** and enter:
   - `http://localhost:3000/api/auth/callback`
   - `http://127.0.0.1:3000/api/auth/callback`
   - *(If deploying to a production server like Render, add your production HTTPS callback URL here: `https://your-app.onrender.com/api/auth/callback`)*.
5. Click **Create**. A dialog showing your Client ID and Client Secret will appear.
6. Click **Download JSON** in the dialog.
7. Rename the downloaded file to **`client_secrets.json`** and place it in the root folder of this project (`c:\Users\siddh\Downloads\Farewell\client_secrets.json`).

### Step C: Configure Folder ID & Environment Variables
1. Open your personal **Google Drive**.
2. Create or select the folder where photos should go.
3. Copy the **Folder ID** from your browser's address bar (it is the long string of characters after `/folders/`).
4. Open the `.env` file in the project root and fill in `DRIVE_FOLDER_ID`, `ADMIN_PASSWORD`, and a session `SECRET_KEY`:
   ```env
   PORT=3000
   DRIVE_FOLDER_ID=your_copied_folder_id_here
   ADMIN_PASSWORD=admin123
   SECRET_KEY=enter_any_random_string_here_for_sessions
   ```

---

## 2. Local Setup & Running

1. **Install python packages**:
   Open a terminal in the project directory and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**:
   ```bash
   python server.py
   ```
   The server will start up on `http://localhost:3000`.

3. **Complete One-Time Authorization**:
   - Open **`http://localhost:3000/admin`** on your computer.
   - Enter your `ADMIN_PASSWORD` (default: `admin123`) to log in.
   - You will see a warning card: *"Google Drive Link Required"*.
   - Click **Link Google Account**. This will redirect you to Google's sign-in page.
   - Select **your target personal Google Drive email address** (the test user you added in Step A).
   - If Google shows a warning saying "Google hasn't verified this app," click **Advanced** > **Go to Event Camera (unsafe)**.
   - Click **Continue** to grant the app permission.
   - You will be redirected back to the Admin Panel showing **"Google Drive Linked"** (green checkmark).
   - The server has created a **`token.json`** file in the root directory.

4. **Start Snapping**:
   Open `http://localhost:3000` on your browser, take a photo, and verify it uploads directly into your personal Drive folder!

---

## 3. Cloud Deployment (Option A - Recommended)

Deploying to the cloud keeps the app online 24/7.

### Deploying to Render
1. Push this directory to your personal GitHub repository. Make sure `token.json` is **not** pushed to Git for security (we will handle it dynamically).
2. Log into **[Render](https://render.com/)** and click **New** > **Web Service**.
3. Link your GitHub repository.
4. Select environment: **Python 3**.
5. Set the Build Command: `pip install -r requirements.txt`
6. Set the Start Command: `python server.py`
7. Click **Advanced** and add the following Environment Variables:
   - `DRIVE_FOLDER_ID`: Your Google Drive Folder ID.
   - `ADMIN_PASSWORD`: Secret code to access the admin panel.
   - `SECRET_KEY`: Any random text string.
   - `GOOGLE_CLIENT_SECRETS`: Paste the entire text content of your local `client_secrets.json` file here (raw JSON).
8. Click **Deploy**. Copy your new HTTPS URL (e.g. `https://your-app.onrender.com`).
9. Go to your **Google Cloud Console** > **Credentials**, edit your OAuth Client ID, and add `https://your-app.onrender.com/api/auth/callback` to the **Authorized redirect URIs**.
10. Open `https://your-app.onrender.com/admin` in your browser, log in, and click **Link Google Account** to generate the production `token.json` state.

---

## 4. Compiling the Android APK

You can wrap your deployed Web App inside a native Android APK:

1. Open **Android Studio** on your PC.
2. Select **Open** and choose the `android-wrapper` folder inside this directory.
3. Open the file: [MainActivity.java](file:///c:/Users/siddh/Downloads/Farewell/android-wrapper/app/src/main/java/com/event/camera/MainActivity.java).
4. Replace the URL inside `webView.loadUrl("https://your-event-camera-app.onrender.com");` with your actual Render/Railway HTTPS URL.
5. In the top toolbar, select **Build** > **Build Bundle(s) / APK(s)** > **Build APK(s)**.
6. When compilation completes, locate the APK file at: `android-wrapper/app/build/outputs/apk/debug/app-debug.apk`.
