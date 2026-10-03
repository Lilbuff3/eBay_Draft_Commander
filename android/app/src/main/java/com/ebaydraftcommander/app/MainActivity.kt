package com.ebaydraftcommander.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.ClipData
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.view.View
import android.view.WindowManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.widget.RadioButton
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import com.ebaydraftcommander.app.databinding.ActivityMainBinding
import com.ebaydraftcommander.app.databinding.DialogServerConfigBinding
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var serverConfigManager: ServerConfigManager
    private lateinit var nativeBridge: NativeBridge

    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private var cameraImageUri: Uri? = null

    private var cameraPermissionCallback: ((Boolean) -> Unit)? = null
    private var backPressedTime = 0L

    private lateinit var cameraPermissionLauncher: ActivityResultLauncher<String>
    private lateinit var fileChooserLauncher: ActivityResultLauncher<Intent>
    private lateinit var cameraCaptureLauncher: ActivityResultLauncher<Uri>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        serverConfigManager = ServerConfigManager(this)
        nativeBridge = NativeBridge(this, serverConfigManager)

        initActivityResults()
        initBackNavigation()
        initViews()
        initWebView()

        handleIncomingShareIntent(intent)
        loadApp()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingShareIntent(intent)
    }

    private fun initActivityResults() {
        cameraPermissionLauncher = registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { isGranted ->
            cameraPermissionCallback?.invoke(isGranted)
            cameraPermissionCallback = null
        }

        fileChooserLauncher = registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { result ->
            val callback = filePathCallback ?: return@registerForActivityResult
            filePathCallback = null

            if (result.resultCode == RESULT_OK) {
                val data = result.data
                val results = mutableListOf<Uri>()

                // Check for camera output
                cameraImageUri?.let { uri ->
                    val file = File(uri.path ?: "")
                    if (file.exists() && file.length() > 0) {
                        results.add(uri)
                    }
                }

                // Check for file chooser output
                if (data != null) {
                    val clipData: ClipData? = data.clipData
                    if (clipData != null) {
                        for (i in 0 until clipData.itemCount) {
                            results.add(clipData.getItemAt(i).uri)
                        }
                    } else if (data.data != null) {
                        data.data?.let { results.add(it) }
                    }
                }

                callback.onReceiveValue(if (results.isNotEmpty()) results.toTypedArray() else null)
            } else {
                callback.onReceiveValue(null)
            }
            cameraImageUri = null
        }

        cameraCaptureLauncher = registerForActivityResult(
            ActivityResultContracts.TakePicture()
        ) { success ->
            val callback = filePathCallback ?: return@registerForActivityResult
            filePathCallback = null

            if (success && cameraImageUri != null) {
                callback.onReceiveValue(arrayOf(cameraImageUri!!))
            } else {
                callback.onReceiveValue(null)
            }
            cameraImageUri = null
        }
    }

    private fun initBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webView.canGoBack()) {
                    binding.webView.goBack()
                } else {
                    val currentTime = System.currentTimeMillis()
                    if (currentTime - backPressedTime < 2000) {
                        finish()
                    } else {
                        backPressedTime = currentTime
                        Toast.makeText(
                            this@MainActivity,
                            "Press back again to exit",
                            Toast.LENGTH_SHORT
                        ).show()
                    }
                }
            }
        })
    }

    private fun initViews() {
        binding.swipeRefresh.setColorSchemeResources(R.color.brand_primary)
        binding.swipeRefresh.setOnRefreshListener {
            binding.webView.reload()
        }

        binding.btnRetry.setOnClickListener {
            binding.errorLayout.visibility = View.GONE
            binding.webView.visibility = View.VISIBLE
            loadApp()
        }

        binding.btnServerSettings.setOnClickListener {
            showServerConfigDialog()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun initWebView() {
        with(binding.webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = true
            allowContentAccess = true
            loadWithOverviewMode = true
            useWideViewPort = true
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            }

            userAgentString = "$userAgentString eBayDraftCommander-Android/1.0"
        }

        binding.webView.addJavascriptInterface(nativeBridge, "AndroidBridge")
        binding.webView.webViewClient = CommanderWebViewClient(this, serverConfigManager)
        binding.webView.webChromeClient = CommanderWebChromeClient(this)

        // Disable swipe refresh when scrolled down
        binding.webView.viewTreeObserver.addOnScrollChangedListener {
            binding.swipeRefresh.isEnabled = (binding.webView.scrollY == 0)
        }
    }

    fun loadApp() {
        val targetUrl = serverConfigManager.currentBaseUrl
        binding.webView.loadUrl(targetUrl)
    }

    fun onProgressChanged(progress: Int) {
        if (progress in 1..99) {
            binding.progressBar.visibility = View.VISIBLE
            binding.progressBar.progress = progress
        } else {
            binding.progressBar.visibility = View.GONE
            binding.swipeRefresh.isRefreshing = false
        }
    }

    fun showError(detail: String) {
        binding.progressBar.visibility = View.GONE
        binding.swipeRefresh.isRefreshing = false
        binding.webView.visibility = View.GONE
        binding.errorLayout.visibility = View.VISIBLE
        binding.textErrorDetail.text = getString(R.string.connection_error_msg) + "\n\nDetails: " + detail
    }

    fun hideError() {
        binding.errorLayout.visibility = View.GONE
        binding.webView.visibility = View.VISIBLE
    }

    fun setScreenWakeLock(enabled: Boolean) {
        if (enabled) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    fun requestCameraPermission(callback: (Boolean) -> Unit) {
        cameraPermissionCallback = callback
        cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
    }

    fun handleFileChooser(
        callback: ValueCallback<Array<Uri>>,
        params: WebChromeClient.FileChooserParams
    ): Boolean {
        filePathCallback?.onReceiveValue(null)
        filePathCallback = callback

        val isCapture = params.isCaptureEnabled
        val mimeTypes = params.acceptTypes

        val isImage = mimeTypes.isEmpty() || mimeTypes.any { it.contains("image") }

        if (isCapture && isImage) {
            // Direct camera capture
            launchCameraOnly()
        } else {
            // Combined camera + gallery picker intent
            launchCombinedPicker(params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE)
        }
        return true
    }

    private fun launchCameraOnly() {
        val photoFile = createImageFile()
        if (photoFile != null) {
            cameraImageUri = FileProvider.getUriForFile(
                this,
                "${applicationContext.packageName}.fileprovider",
                photoFile
            )
            cameraCaptureLauncher.launch(cameraImageUri!!)
        } else {
            filePathCallback?.onReceiveValue(null)
            filePathCallback = null
        }
    }

    private fun launchCombinedPicker(allowMultiple: Boolean) {
        val galleryIntent = Intent(Intent.ACTION_GET_CONTENT).apply {
            type = "image/*"
            if (allowMultiple) {
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            }
            addCategory(Intent.CATEGORY_OPENABLE)
        }

        val cameraIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        val photoFile = createImageFile()
        if (photoFile != null) {
            cameraImageUri = FileProvider.getUriForFile(
                this,
                "${applicationContext.packageName}.fileprovider",
                photoFile
            )
            cameraIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraImageUri)
        }

        val chooserIntent = Intent.createChooser(galleryIntent, "Select Photos or Camera")
        chooserIntent.putExtra(Intent.EXTRA_INITIAL_INTENTS, arrayOf(cameraIntent))

        fileChooserLauncher.launch(chooserIntent)
    }

    private fun createImageFile(): File? {
        return try {
            val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: cacheDir
            File.createTempFile("DC_${timeStamp}_", ".jpg", storageDir)
        } catch (_: Exception) {
            null
        }
    }

    private fun handleIncomingShareIntent(intent: Intent?) {
        if (intent == null) return
        val action = intent.action
        val type = intent.type ?: return

        if (!type.startsWith("image/")) return

        val sharedUris = mutableListOf<Uri>()

        if (Intent.ACTION_SEND == action) {
            val imageUri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(Intent.EXTRA_STREAM) as? Uri
            }
            imageUri?.let { sharedUris.add(it) }
        } else if (Intent.ACTION_SEND_MULTIPLE == action) {
            val list = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)
            }
            list?.let { sharedUris.addAll(it) }
        }

        if (sharedUris.isNotEmpty()) {
            Toast.makeText(
                this,
                "Received ${sharedUris.size} shared image(s)",
                Toast.LENGTH_SHORT
            ).show()
            // When images are shared from native gallery, direct user to #create
            val createUrl = serverConfigManager.currentBaseUrl + "#create"
            binding.webView.loadUrl(createUrl)
        }
    }

    fun showServerConfigDialog() {
        val dialogBinding = DialogServerConfigBinding.inflate(layoutInflater)

        when (serverConfigManager.serverMode) {
            ServerMode.TAILSCALE -> dialogBinding.radioTailscale.isChecked = true
            ServerMode.LAN -> dialogBinding.radioLan.isChecked = true
            ServerMode.CUSTOM -> dialogBinding.radioCustom.isChecked = true
        }

        dialogBinding.editServerUrl.setText(serverConfigManager.customUrl)
        dialogBinding.editApiKey.setText(serverConfigManager.apiKey)

        val updateUrlInputState = {
            val isCustom = dialogBinding.radioCustom.isChecked
            dialogBinding.inputLayoutUrl.isEnabled = isCustom
            if (!isCustom) {
                val placeholder = if (dialogBinding.radioTailscale.isChecked) {
                    ServerConfigManager.DEFAULT_TAILSCALE_URL
                } else {
                    ServerConfigManager.DEFAULT_LAN_URL
                }
                dialogBinding.editServerUrl.setText(placeholder)
            }
        }
        updateUrlInputState()

        dialogBinding.radioGroupServerMode.setOnCheckedChangeListener { _, _ ->
            updateUrlInputState()
        }

        dialogBinding.btnTestHealth.setOnClickListener {
            dialogBinding.textHealthResult.visibility = View.VISIBLE
            dialogBinding.textHealthResult.text = "Testing connection..."
            dialogBinding.textHealthResult.setTextColor(ContextCompat.getColor(this, R.color.brand_text_muted))

            lifecycleScope.launch {
                val (ok, msg) = serverConfigManager.testConnection()
                if (ok) {
                    dialogBinding.textHealthResult.text = "✓ " + getString(R.string.connection_ok)
                    dialogBinding.textHealthResult.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.brand_primary))
                } else {
                    dialogBinding.textHealthResult.text = "✗ " + getString(R.string.connection_failed) + " ($msg)"
                    dialogBinding.textHealthResult.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.brand_error))
                }
            }
        }

        AlertDialog.Builder(this)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.save) { _, _ ->
                val selectedMode = when {
                    dialogBinding.radioTailscale.isChecked -> ServerMode.TAILSCALE
                    dialogBinding.radioLan.isChecked -> ServerMode.LAN
                    else -> ServerMode.CUSTOM
                }
                serverConfigManager.serverMode = selectedMode
                if (selectedMode == ServerMode.CUSTOM) {
                    serverConfigManager.customUrl = dialogBinding.editServerUrl.text.toString().trim()
                }
                serverConfigManager.apiKey = dialogBinding.editApiKey.text.toString().trim()

                Toast.makeText(this, "Server settings saved", Toast.LENGTH_SHORT).show()
                hideError()
                loadApp()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }
}
