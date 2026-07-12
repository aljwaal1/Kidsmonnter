package com.explapp.kidstimeguard

import android.app.*
import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.*
import android.graphics.Color
import android.net.Uri
import android.os.*
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.core.app.NotificationCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.text.SimpleDateFormat
import java.util.*

private const val PREFS_NAME = "kidsmonnter"
private const val FAILED_ATTEMPTS_KEY = "failed_pin_attempts"
private const val PARENT_EMAIL_KEY = "parent_email"
private const val DEFAULT_PARENT_EMAIL = "yaya15112016@gmail.com"
private const val MAX_FAILED_ATTEMPTS = 50
private const val GUARD_CHANNEL_ID = "kidsmonnter_guard"
private const val ALERT_CHANNEL_ID = "kidsmonnter_security_alerts"
private const val NOTIFICATION_ID = 1001

private fun Context.deviceAdminComponent() =
    ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)

private fun Context.isDeviceOwner(): Boolean =
    (getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager)
        .isDeviceOwnerApp(packageName)

private fun Context.configureDeviceOwnerPolicies() {
    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!dpm.isDeviceOwnerApp(packageName)) return
    val admin = deviceAdminComponent()
    dpm.setLockTaskPackages(admin, arrayOf(packageName))
    dpm.setUninstallBlocked(admin, packageName, true)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
        dpm.setStatusBarDisabled(admin, true)
    }
}

private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
private fun timestamp(): String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())

private fun Context.guardPrefs(): SharedPreferences =
    getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

private fun parentEmail(prefs: SharedPreferences): String =
    prefs.getString(PARENT_EMAIL_KEY, DEFAULT_PARENT_EMAIL).orEmpty().ifBlank { DEFAULT_PARENT_EMAIL }

private fun Context.startMonitorService() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent)
    else startService(intent)
}

private fun readFailedAttempts(prefs: SharedPreferences): List<Map<String, String>> =
    prefs.getString(FAILED_ATTEMPTS_KEY, "")
        .orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .mapNotNull { line ->
            val parts = line.split("|", limit = 2)
            if (parts.size != 2) null else mapOf("time" to parts[0], "source" to parts[1])
        }
        .toList()
        .asReversed()

private fun securityReportBody(prefs: SharedPreferences): String {
    val attempts = readFailedAttempts(prefs)
    return buildString {
        appendLine("تقرير حارس وقت الأطفال")
        appendLine("تاريخ التقرير: ${timestamp()}")
        appendLine("عدد المحاولات الفاشلة: ${attempts.size}")
        appendLine()
        if (attempts.isEmpty()) {
            appendLine("لا توجد محاولات PIN فاشلة مسجلة.")
        } else {
            attempts.forEachIndexed { index, item ->
                appendLine("${index + 1}. ${item["time"]} - ${item["source"]}")
            }
        }
    }
}

private fun emailIntent(prefs: SharedPreferences, subject: String): Intent =
    Intent(Intent.ACTION_SENDTO).apply {
        data = Uri.parse("mailto:")
        putExtra(Intent.EXTRA_EMAIL, arrayOf(parentEmail(prefs)))
        putExtra(Intent.EXTRA_SUBJECT, subject)
        putExtra(Intent.EXTRA_TEXT, securityReportBody(prefs))
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

private fun openSecurityEmail(context: Context, prefs: SharedPreferences, subject: String) {
    try {
        context.startActivity(emailIntent(prefs, subject))
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, "لا يوجد تطبيق بريد إلكتروني مثبت", Toast.LENGTH_LONG).show()
    }
}

private fun createSecurityChannel(context: Context) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(
                ALERT_CHANNEL_ID,
                "تنبيهات محاولات تجاوز القفل",
                NotificationManager.IMPORTANCE_HIGH
            ).apply { description = "تنبيه أمني عند إدخال رمز ولي الأمر بشكل خاطئ" }
        )
    }
}

private fun showSecurityAlert(context: Context, prefs: SharedPreferences, source: String) {
    createSecurityChannel(context)
    val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    val pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT or
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0
    val pending = PendingIntent.getActivity(
        context,
        (System.currentTimeMillis() % Int.MAX_VALUE).toInt(),
        emailIntent(prefs, "تنبيه أمني: محاولة PIN فاشلة"),
        pendingFlags
    )
    val notification = NotificationCompat.Builder(context, ALERT_CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_dialog_alert)
        .setContentTitle("محاولة PIN غير صحيحة")
        .setContentText(source)
        .setStyle(
            NotificationCompat.BigTextStyle().bigText(
                "تم تسجيل محاولة فاشلة: $source\nاضغط لإرسال سجل المحاولات إلى ${parentEmail(prefs)}"
            )
        )
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .setAutoCancel(true)
        .setContentIntent(pending)
        .addAction(android.R.drawable.ic_dialog_email, "إرسال التقرير", pending)
        .build()
    manager.notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notification)
}

private fun recordFailedAttempt(context: Context, prefs: SharedPreferences, source: String) {
    val entries = prefs.getString(FAILED_ATTEMPTS_KEY, "")
        .orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .toMutableList()
    entries.add("${timestamp()}|$source")
    prefs.edit().putString(FAILED_ATTEMPTS_KEY, entries.takeLast(MAX_FAILED_ATTEMPTS).joinToString("\n")).apply()
    showSecurityAlert(context, prefs, source)
}

class MainActivity : FlutterActivity() {
    private val channel = "kidsmonnter/control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel)
            .setMethodCallHandler { call, result ->
                val prefs = guardPrefs()
                when (call.method) {
                    "getDevicePolicyStatus" -> {
                        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                        result.success(mapOf(
                            "deviceOwner" to dpm.isDeviceOwnerApp(packageName),
                            "adminActive" to dpm.isAdminActive(deviceAdminComponent()),
                            "lockTaskPermitted" to dpm.isLockTaskPermitted(packageName)
                        ))
                    }
                    "configureDeviceOwner" -> {
                        if (!isDeviceOwner()) {
                            result.error("NOT_DEVICE_OWNER", "App is not provisioned as Device Owner", null)
                        } else {
                            configureDeviceOwnerPolicies()
                            result.success(true)
                        }
                    }
                    "setPin" -> {
                        val pin = call.argument<String>("pin").orEmpty()
                        if (pin.length != 6 || pin.any { !it.isDigit() }) {
                            result.error("INVALID_PIN", "PIN must be 6 digits", null)
                        } else {
                            prefs.edit().putString("parent_pin", pin).apply()
                            result.success(true)
                        }
                    }
                    "hasPin" -> result.success(prefs.getString("parent_pin", "").orEmpty().length == 6)
                    "verifyPin" -> {
                        val pin = call.argument<String>("pin").orEmpty()
                        val valid = pin == prefs.getString("parent_pin", "")
                        if (!valid) recordFailedAttempt(this, prefs, "تأكيد إعدادات ولي الأمر")
                        result.success(valid)
                    }
                    "setParentEmail" -> {
                        val email = call.argument<String>("email")?.trim().orEmpty()
                        if (!android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
                            result.error("INVALID_EMAIL", "عنوان البريد الإلكتروني غير صحيح", null)
                        } else {
                            prefs.edit().putString(PARENT_EMAIL_KEY, email).apply()
                            result.success(true)
                        }
                    }
                    "getParentEmail" -> result.success(parentEmail(prefs))
                    "sendSecurityReport" -> {
                        openSecurityEmail(this, prefs, "تقرير محاولات PIN")
                        result.success(true)
                    }
                    "startProtection" -> {
                        val minutes = call.argument<Int>("minutes") ?: 60
                        prefs.edit()
                            .putInt("daily_minutes", minutes.coerceIn(1, 1440))
                            .putBoolean("enabled", true)
                            .putString("date", today())
                            .remove("unlocked_date")
                            .apply()
                        startMonitorService()
                        result.success(true)
                    }
                    "stopProtection" -> {
                        val pin = call.argument<String>("pin").orEmpty()
                        if (pin != prefs.getString("parent_pin", "")) {
                            recordFailedAttempt(this, prefs, "إيقاف الحماية")
                            result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                        } else {
                            prefs.edit().putBoolean("enabled", false).apply()
                            stopService(Intent(this, MonitorService::class.java))
                            result.success(true)
                        }
                    }
                    "addTime" -> {
                        val pin = call.argument<String>("pin").orEmpty()
                        val minutes = call.argument<Int>("minutes") ?: 0
                        if (pin != prefs.getString("parent_pin", "")) {
                            recordFailedAttempt(this, prefs, "إضافة وقت")
                            result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                        } else {
                            val used = prefs.getInt("used_seconds", 0)
                            prefs.edit()
                                .putInt("used_seconds", (used - minutes.coerceAtLeast(0) * 60).coerceAtLeast(0))
                                .remove("unlocked_date")
                                .apply()
                            result.success(true)
                        }
                    }
                    "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                    "clearFailedAttempts" -> {
                        val pin = call.argument<String>("pin").orEmpty()
                        if (pin != prefs.getString("parent_pin", "")) {
                            recordFailedAttempt(this, prefs, "مسح سجل المحاولات")
                            result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                        } else {
                            prefs.edit().remove(FAILED_ATTEMPTS_KEY).apply()
                            result.success(true)
                        }
                    }
                    "getStatus" -> result.success(
                        mapOf(
                            "enabled" to prefs.getBoolean("enabled", false),
                            "usedSeconds" to prefs.getInt("used_seconds", 0),
                            "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                            "hasPin" to (prefs.getString("parent_pin", "").orEmpty().length == 6),
                            "failedAttempts" to readFailedAttempts(prefs).size,
                            "parentEmail" to parentEmail(prefs),
                            "overlayAllowed" to Settings.canDrawOverlays(this)
                        )
                    )
                    "openOverlaySettings" -> {
                        startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
                        result.success(true)
                    }
                    "canDrawOverlays" -> result.success(Settings.canDrawOverlays(this))
                    else -> result.notImplemented()
                }
            }
    }
}

class MonitorService : Service() {
    private val prefs by lazy { guardPrefs() }
    private val handler = Handler(Looper.getMainLooper())
    private var screenOn = true
    private var overlayWarningRecorded = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_ON, Intent.ACTION_USER_PRESENT -> {
                    screenOn = true
                    enforceLockIfNeeded()
                }
                Intent.ACTION_SCREEN_OFF -> screenOn = false
            }
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            resetIfNewDay()
            val enabled = prefs.getBoolean("enabled", false)
            if (enabled) {
                monitorOverlayPermission()
                val unlockedToday = prefs.getString("unlocked_date", "") == today()
                if (screenOn && !unlockedToday) {
                    val limit = prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
                    val current = prefs.getInt("used_seconds", 0)
                    val used = if (current < limit) current + 1 else current
                    if (used != current) prefs.edit().putInt("used_seconds", used).apply()
                    if (used == (limit - 300).coerceAtLeast(1)) notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
                    if (used == (limit - 60).coerceAtLeast(1)) notifyWarning("تبقّت دقيقة واحدة من وقت الهاتف")
                    if (used >= limit) showLock()
                }
            }
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createGuardChannel()
        screenOn = (getSystemService(POWER_SERVICE) as PowerManager).isInteractive
        registerReceiver(screenReceiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_USER_PRESENT)
        })
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        handler.post(ticker)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        enforceLockIfNeeded()
        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (prefs.getBoolean("enabled", false)) {
            val restart = PendingIntent.getService(
                this,
                991,
                Intent(this, MonitorService::class.java),
                PendingIntent.FLAG_ONE_SHOT or
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0
            )
            (getSystemService(ALARM_SERVICE) as AlarmManager).set(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 1500,
                restart
            )
        }
        super.onTaskRemoved(rootIntent)
    }

    override fun onBind(intent: Intent?) = null

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
        if (prefs.getBoolean("enabled", false)) {
            Handler(Looper.getMainLooper()).postDelayed({ applicationContext.startMonitorService() }, 1000)
        }
        super.onDestroy()
    }

    private fun resetIfNewDay() {
        val value = today()
        if (prefs.getString("date", "") != value) {
            prefs.edit()
                .putString("date", value)
                .putInt("used_seconds", 0)
                .remove("unlocked_date")
                .apply()
            overlayWarningRecorded = false
        }
    }

    private fun isTimeFinished(): Boolean {
        if (!prefs.getBoolean("enabled", false)) return false
        if (prefs.getString("unlocked_date", "") == today()) return false
        val limit = prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
        return prefs.getInt("used_seconds", 0) >= limit
    }

    private fun enforceLockIfNeeded() {
        if (screenOn && isTimeFinished()) showLock()
    }

    private fun showLock() {
        if (!Settings.canDrawOverlays(this)) return
        try {
            startActivity(Intent(this, LockActivity::class.java).apply {
                addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or
                        Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS
                )
            })
        } catch (_: Exception) {}
    }

    private fun monitorOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            if (!overlayWarningRecorded) {
                overlayWarningRecorded = true
                recordFailedAttempt(this, prefs, "تم إلغاء صلاحية شاشة القفل")
            }
        } else {
            overlayWarningRecorded = false
        }
    }

    private fun notifyWarning(text: String) {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(1002, buildGuardNotification(text))
    }

    private fun buildGuardNotification(text: String): Notification =
        NotificationCompat.Builder(this, GUARD_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("حارس وقت الأطفال")
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(false)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

    private fun createGuardChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(
                NotificationChannel(
                    GUARD_CHANNEL_ID,
                    "حماية وقت الهاتف",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply { setShowBadge(false) }
            )
        }
    }
}

class LockActivity : Activity() {
    private val prefs by lazy { guardPrefs() }
    private val handler = Handler(Looper.getMainLooper())
    private var authorizedExit = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configureDeviceOwnerPolicies()
        val dpm = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        if (dpm.isLockTaskPermitted(packageName)) startLockTask()
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
        )
        if (!shouldRemainLocked()) {
            finish()
            return
        }
        showImmersive()
        try { startLockTask() } catch (_: Exception) {}
        setContentView(buildLockView())
    }

    override fun onResume() {
        super.onResume()
        showImmersive()
        if (!shouldRemainLocked()) {
            authorizedExit = true
            finishAndRemoveTask()
        }
    }

    override fun onPause() {
        super.onPause()
        if (!authorizedExit && shouldRemainLocked()) {
            handler.postDelayed({
                try {
                    startActivity(Intent(this, LockActivity::class.java).apply {
                        addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    })
                } catch (_: Exception) {}
            }, 250)
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) showImmersive()
    }

    private fun shouldRemainLocked(): Boolean {
        if (!prefs.getBoolean("enabled", false)) return false
        if (prefs.getString("unlocked_date", "") == today()) return false
        return prefs.getInt("used_seconds", 0) >= prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
    }

    private fun showImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun buildLockView(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(44, 44, 44, 44)
            setBackgroundColor(Color.rgb(25, 42, 39))
        }
        root.addView(TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = "يمكن لولي الأمر إضافة وقت أو فتح الهاتف لبقية اليوم."
            textSize = 17f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 20, 0, 30)
        })

        val pinInput = EditText(this).apply {
            hint = "PIN ولي الأمر"
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
            gravity = Gravity.CENTER
            filters = arrayOf(android.text.InputFilter.LengthFilter(6))
        }
        val status = TextView(this).apply {
            setTextColor(Color.rgb(255, 180, 170))
            gravity = Gravity.CENTER
            setPadding(0, 12, 0, 12)
        }
        root.addView(pinInput, LinearLayout.LayoutParams(-1, -2))
        root.addView(status, LinearLayout.LayoutParams(-1, -2))

        root.addView(Button(this).apply {
            text = "إضافة 15 دقيقة"
            setOnClickListener {
                if (verifyPin(pinInput.text.toString(), "فتح القفل وإضافة 15 دقيقة", status)) {
                    val used = prefs.getInt("used_seconds", 0)
                    prefs.edit().putInt("used_seconds", (used - 900).coerceAtLeast(0)).apply()
                    exitLock()
                }
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        root.addView(Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            setOnClickListener {
                if (verifyPin(pinInput.text.toString(), "فتح الهاتف لبقية اليوم", status)) {
                    prefs.edit().putString("unlocked_date", today()).apply()
                    exitLock()
                }
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        return root
    }

    private fun verifyPin(pin: String, source: String, status: TextView): Boolean {
        val valid = pin.length == 6 && pin == prefs.getString("parent_pin", "")
        if (!valid) {
            recordFailedAttempt(this, prefs, source)
            status.text = "رمز ولي الأمر غير صحيح. تم تسجيل المحاولة."
        }
        return valid
    }

    private fun exitLock() {
        authorizedExit = true
        try { stopLockTask() } catch (_: Exception) {}
        finishAndRemoveTask()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() = Unit
}

class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.guardPrefs()
        if (prefs.getBoolean("enabled", false)) context.startMonitorService()
    }
}
