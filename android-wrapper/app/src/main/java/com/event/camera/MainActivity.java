package com.event.camera;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.widget.Toast;
import java.io.OutputStream;

public class MainActivity extends AppCompatActivity {

    private static final int CAMERA_PERMISSION_CODE = 100;
    private WebView webView;
    private PermissionRequest pendingPermissionRequest;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Dynamic WebView creation (avoids requiring layout XML)
        webView = new WebView(this);
        setContentView(webView);

        // Configure standard WebView settings
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setLoadsImagesAutomatically(true);
        
        // Ensure links open inside the WebView rather than launching external browser
        webView.setWebViewClient(new WebViewClient());

        // Register JavaScript interface bridge for local photo downloads
        webView.addJavascriptInterface(new WebAppInterface(this), "AndroidBridge");

        // Override WebChromeClient to handle HTML5 permission requests (Camera and Audio)
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                pendingPermissionRequest = request;
                checkPermissionsAndGrant();
            }
        });

        // Load your deployed Web App URL
        webView.loadUrl("https://farewell-tl8b.onrender.com");
    }

    private void checkPermissionsAndGrant() {
        boolean hasCamera = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) 
                == PackageManager.PERMISSION_GRANTED;
        boolean hasAudio = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
                == PackageManager.PERMISSION_GRANTED;

        if (hasCamera && hasAudio) {
            grantWebViewPermissions();
        } else {
            // Request both camera and audio record permissions
            ActivityCompat.requestPermissions(this, 
                    new String[]{Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO}, 
                    CAMERA_PERMISSION_CODE);
        }
    }

    private void grantWebViewPermissions() {
        if (pendingPermissionRequest != null) {
            java.util.ArrayList<String> grantedResources = new java.util.ArrayList<>();
            for (String resource : pendingPermissionRequest.getResources()) {
                if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource) &&
                        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    grantedResources.add(resource);
                }
                if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource) &&
                        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    grantedResources.add(resource);
                }
            }
            if (!grantedResources.isEmpty()) {
                pendingPermissionRequest.grant(grantedResources.toArray(new String[0]));
            } else {
                pendingPermissionRequest.deny();
            }
            pendingPermissionRequest = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == CAMERA_PERMISSION_CODE) {
            grantWebViewPermissions();
        } else if (requestCode == 200) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Toast.makeText(this, "Storage permission granted!", Toast.LENGTH_LONG).show();
            } else {
                Toast.makeText(this, "Storage permission is required to save files to this device.", Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    public void onBackPressed() {
        // Handle back button navigation inside the web history
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    // JavaScript Bridge Interface implementation
    public class WebAppInterface {
        private Context mContext;

        WebAppInterface(Context c) {
            mContext = c;
        }

        @JavascriptInterface
        public void saveImageToGallery(String base64Image, String filename) {
            try {
                // Check write permission for Android 9 and below
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                    if (ContextCompat.checkSelfPermission(mContext, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                            != PackageManager.PERMISSION_GRANTED) {
                        ActivityCompat.requestPermissions((MainActivity) mContext,
                                new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE},
                                200);
                        showToast("Please grant storage permission and try again.");
                        return;
                    }
                }

                // Remove data URL prefix if present
                if (base64Image.startsWith("data:image")) {
                    base64Image = base64Image.substring(base64Image.indexOf(",") + 1);
                }

                // Decode base64 string
                byte[] decodedString = Base64.decode(base64Image, Base64.DEFAULT);
                Bitmap bitmap = BitmapFactory.decodeByteArray(decodedString, 0, decodedString.length);

                if (bitmap == null) {
                    showToast("Failed to process captured image.");
                    return;
                }

                OutputStream fos;
                Uri imageUri = null;
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DISPLAY_NAME, filename);
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    // Android 10+ uses MediaStore sandbox (no storage permission required)
                    values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_DCIM + "/EventCamera");
                    values.put(MediaStore.Images.Media.IS_PENDING, 1);
                    imageUri = mContext.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                } else {
                    // Pre-Q fallback
                    imageUri = mContext.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                }

                if (imageUri != null) {
                    fos = mContext.getContentResolver().openOutputStream(imageUri);
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 100, fos);
                    if (fos != null) {
                        fos.close();
                    }

                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        values.clear();
                        values.put(MediaStore.Images.Media.IS_PENDING, 0);
                        mContext.getContentResolver().update(imageUri, values, null, null);
                    }

                    showToast("Photo saved to Gallery!");
                } else {
                    showToast("Failed to save image to storage.");
                }

            } catch (Exception e) {
                e.printStackTrace();
                showToast("Error saving image: " + e.getMessage());
            }
        }

        @JavascriptInterface
        public void saveVideoToGallery(String base64Video, String filename) {
            try {
                // Check write permission for Android 9 and below
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                    if (ContextCompat.checkSelfPermission(mContext, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                            != PackageManager.PERMISSION_GRANTED) {
                        ActivityCompat.requestPermissions((MainActivity) mContext,
                                new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE},
                                200);
                        showToast("Please grant storage permission and try again.");
                        return;
                    }
                }

                // Remove data URL prefix if present
                if (base64Video.startsWith("data:video")) {
                    base64Video = base64Video.substring(base64Video.indexOf(",") + 1);
                }

                // Decode base64 string
                byte[] decodedString = Base64.decode(base64Video, Base64.DEFAULT);

                OutputStream fos;
                Uri videoUri = null;
                ContentValues values = new ContentValues();
                values.put(MediaStore.Video.Media.DISPLAY_NAME, filename);
                values.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    values.put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_DCIM + "/EventCamera");
                    values.put(MediaStore.Video.Media.IS_PENDING, 1);
                    videoUri = mContext.getContentResolver().insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values);
                } else {
                    videoUri = mContext.getContentResolver().insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values);
                }

                if (videoUri != null) {
                    fos = mContext.getContentResolver().openOutputStream(videoUri);
                    if (fos != null) {
                        fos.write(decodedString);
                        fos.close();
                    }

                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        values.clear();
                        values.put(MediaStore.Video.Media.IS_PENDING, 0);
                        mContext.getContentResolver().update(videoUri, values, null, null);
                    }

                    showToast("Video saved to Gallery!");
                } else {
                    showToast("Failed to save video to storage.");
                }

            } catch (Exception e) {
                e.printStackTrace();
                showToast("Error saving video: " + e.getMessage());
            }
        }

        private void showToast(final String message) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(mContext, message, Toast.LENGTH_SHORT).show();
                }
            });
        }
    }
}
