package com.example.smsrelay

import android.Manifest
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {
    private lateinit var statusTabButton: Button
    private lateinit var toolsTabButton: Button
    private lateinit var statusSection: LinearLayout
    private lateinit var toolsSection: LinearLayout
    private lateinit var permissionValue: TextView
    private lateinit var queueValue: TextView
    private lateinit var connectionValue: TextView
    private lateinit var serverValue: TextView
    private lateinit var clientValue: TextView
    private lateinit var uploadStatus: TextView
    private lateinit var testMessageInput: EditText

    private val requestSmsPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {
        refreshStatus()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = INK
        window.navigationBarColor = INK
        buildUi()
        showTab(Tab.STATUS)
        refreshStatus()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(Menu.NONE, MENU_SETTINGS, Menu.NONE, "Settings")
            .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            MENU_SETTINGS -> {
                showSettingsDialog()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun buildUi() {
        val scrollView = ScrollView(this).apply {
            setBackgroundColor(INK)
        }
        ViewCompat.setOnApplyWindowInsetsListener(scrollView) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 28, 32, 32)
        }
        scrollView.addView(content)

        content.addView(heroTitle())
        content.addView(tabBar())

        statusSection = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        toolsSection = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }

        permissionValue = valueText()
        queueValue = valueText()
        connectionValue = valueText()
        serverValue = valueText()
        clientValue = valueText()
        uploadStatus = valueText()

        statusSection.addView(metricCard("Connection", connectionValue))
        statusSection.addView(metricCard("Queue Size", queueValue))
        statusSection.addView(metricCard("SMS Permission", permissionValue))
        statusSection.addView(metricCard("Server", serverValue))
        statusSection.addView(metricCard("Receiver ID", clientValue))
        statusSection.addView(metricCard("Last Upload", uploadStatus))

        toolsSection.addView(sectionLabel("Test Message"))
        testMessageInput = input("Message body").apply {
            minLines = 4
            setText("SMS Relay encrypted test")
        }
        toolsSection.addView(testMessageInput)
        toolsSection.addView(actionButton("Send Test Message") {
            enqueueTestMessage()
        })
        toolsSection.addView(actionButton("Retry Upload Queue") {
            retryUploadQueue()
        })

        content.addView(statusSection)
        content.addView(toolsSection)

        setContentView(scrollView)
    }

    private fun heroTitle(): LinearLayout {
        val title = TextView(this).apply {
            text = "SMS Relay"
            textSize = 30f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(FOG)
        }
        val subtitle = TextView(this).apply {
            text = "Encrypted forwarding status"
            textSize = 15f
            setTextColor(MUTED)
        }
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 0, 0, 22)
            addView(title)
            addView(subtitle)
        }
    }

    private fun tabBar(): LinearLayout {
        statusTabButton = tabButton("Status") { showTab(Tab.STATUS) }
        toolsTabButton = tabButton("Tools") { showTab(Tab.TOOLS) }
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            background = rounded(SURFACE, 8f, SURFACE_STROKE, 1)
            setPadding(6, 6, 6, 6)
            addView(statusTabButton)
            addView(toolsTabButton)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 18 }
        }
    }

    private fun showTab(tab: Tab) {
        val statusVisible = tab == Tab.STATUS
        statusSection.visibility = if (statusVisible) View.VISIBLE else View.GONE
        toolsSection.visibility = if (statusVisible) View.GONE else View.VISIBLE
        styleTab(statusTabButton, statusVisible)
        styleTab(toolsTabButton, !statusVisible)
    }

    private fun metricCard(label: String, value: TextView): LinearLayout {
        val labelView = TextView(this).apply {
            text = label
            textSize = 13f
            setTextColor(MUTED)
        }
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(SURFACE, 8f, SURFACE_STROKE, 1)
            setPadding(20, 16, 20, 16)
            addView(labelView)
            addView(value)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 12 }
        }
    }

    private fun valueText(): TextView {
        return TextView(this).apply {
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(FOG)
            setPadding(0, 4, 0, 0)
        }
    }

    private fun showSettingsDialog() {
        val stored = SettingsStore(this).getSettings()
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 24, 48, 0)
        }

        val serverUrlInput = input("Server URL").apply { setText(stored.serverUrl) }
        val bearerTokenInput = input("Bearer token").apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setText(stored.bearerToken)
        }
        val showToken = CheckBox(this).apply {
            text = "Show token"
            setOnCheckedChangeListener { _, visible ->
                updateBearerTokenVisibility(bearerTokenInput, visible)
            }
        }
        val clientIdInput = input("Client ID").apply { setText(stored.clientId) }
        val publicKeyInput = input("Server public key PEM").apply {
            inputType = InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            minLines = 8
            gravity = Gravity.TOP or Gravity.START
            setText(stored.serverPublicKeyPem)
        }

        content.addView(sectionLabel("Server URL"))
        content.addView(serverUrlInput)
        content.addView(sectionLabel("Bearer Token"))
        content.addView(bearerTokenInput)
        content.addView(showToken)
        content.addView(sectionLabel("Client ID"))
        content.addView(clientIdInput)
        content.addView(sectionLabel("Server Public Key"))
        content.addView(publicKeyInput)
        content.addView(actionButton("Grant SMS Permission") {
            requestSmsPermission.launch(Manifest.permission.RECEIVE_SMS)
        })
        content.addView(actionButton("Open Battery Settings") {
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        })

        AlertDialog.Builder(this)
            .setTitle("Settings")
            .setView(ScrollView(this).apply { addView(content) })
            .setPositiveButton("Save") { _, _ ->
                SettingsStore(this).save(
                    RelaySettings(
                        serverUrl = serverUrlInput.text.toString(),
                        bearerToken = bearerTokenInput.text.toString(),
                        clientId = clientIdInput.text.toString(),
                        serverPublicKeyPem = publicKeyInput.text.toString(),
                    )
                )
                refreshStatus()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun updateBearerTokenVisibility(input: EditText, visible: Boolean) {
        val cursor = input.selectionStart.coerceAtLeast(0)
        input.inputType = if (visible) {
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
        } else {
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        input.setSelection(cursor.coerceAtMost(input.text.length))
    }

    private fun refreshStatus() {
        lifecycleScope.launch {
            val repository = SmsRepository.get(this@MainActivity)
            val queueLength = withContext(Dispatchers.IO) { repository.queueLength() }
            val latest = withContext(Dispatchers.IO) { repository.latestStatusText() }
            val lastUpload = SettingsStore(this@MainActivity).getLastUploadStatus()
            val settings = SettingsStore(this@MainActivity).getSettings()

            permissionValue.text = if (PermissionHelper.hasSmsPermission(this@MainActivity)) {
                "Granted"
            } else {
                "Missing"
            }
            queueValue.text = queueLength.toString()
            connectionValue.text = lastUpload
            uploadStatus.text = latest
            serverValue.text = settings.serverUrl.ifBlank { "Not configured" }
            clientValue.text = settings.clientId.ifBlank { "Not configured" }
        }
    }

    private fun enqueueTestMessage() {
        lifecycleScope.launch {
            connectionValue.text = "Queuing test message"
            val body = testMessageInput.text.toString()
            val rowId = withContext(Dispatchers.IO) {
                SmsRepository.get(this@MainActivity).enqueueTestSms(body)
            }
            SettingsStore(this@MainActivity).setLastUploadStatus("Test message queued #$rowId")
            connectionValue.text = "Test message queued; upload scheduled"
            SmsUploadWorker.enqueue(this@MainActivity)
            showTab(Tab.STATUS)
            refreshStatus()
            delay(1500)
            refreshStatus()
        }
    }

    private fun retryUploadQueue() {
        lifecycleScope.launch {
            connectionValue.text = "Retry scheduled"
            SettingsStore(this@MainActivity).setLastUploadStatus("Retry scheduled")
            SmsUploadWorker.enqueue(this@MainActivity)
            showTab(Tab.STATUS)
            refreshStatus()
            delay(1500)
            refreshStatus()
        }
    }

    private fun sectionLabel(text: String): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(FOG)
            setPadding(0, 18, 0, 8)
        }
    }

    private fun input(hintText: String): EditText {
        return EditText(this).apply {
            hint = hintText
            setSingleLine(false)
            setSelectAllOnFocus(false)
            setTextColor(FOG)
            setHintTextColor(MUTED)
            background = rounded(SURFACE, 8f, SURFACE_STROKE, 1)
            setPadding(18, 12, 18, 12)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
    }

    private fun tabButton(text: String, onClick: () -> Unit): Button {
        return Button(this).apply {
            this.text = text
            setAllCaps(false)
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
    }

    private fun styleTab(button: Button, selected: Boolean) {
        button.setTextColor(if (selected) INK else FOG)
        button.background = if (selected) rounded(ACCENT, 8f, ACCENT, 0) else rounded(SURFACE, 8f, SURFACE, 0)
    }

    private fun actionButton(text: String, onClick: () -> Unit): Button {
        return Button(this).apply {
            this.text = text
            setAllCaps(false)
            setTextColor(INK)
            typeface = Typeface.DEFAULT_BOLD
            background = rounded(ACCENT, 8f, ACCENT, 0)
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { topMargin = 16 }
        }
    }

    private fun rounded(color: Int, radius: Float, strokeColor: Int, strokeWidth: Int): GradientDrawable {
        return GradientDrawable().apply {
            setColor(color)
            cornerRadius = radius
            if (strokeWidth > 0) setStroke(strokeWidth, strokeColor)
        }
    }

    private enum class Tab { STATUS, TOOLS }

    companion object {
        private const val MENU_SETTINGS = 1
        private val INK = Color.rgb(5, 10, 8)
        private val SURFACE = Color.rgb(12, 24, 19)
        private val SURFACE_STROKE = Color.rgb(28, 64, 49)
        private val ACCENT = Color.rgb(37, 211, 102)
        private val FOG = Color.rgb(234, 255, 243)
        private val MUTED = Color.rgb(149, 184, 164)
    }
}
