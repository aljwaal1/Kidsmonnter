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
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.*

private const val PREFS_NAME = "kidsmonnter"
private const val GUARD_CHANNEL_ID = "kidsmonnter_guard"
private const val ALERT_CHANNEL_ID = "kidsmonnter_security_alerts"
private const val NOTIFICATION_ID = 1001
private const val FAILED_ATTEMPTS_KEY = "failed_pin_attempts"
private const val PARENT_EMAIL_KEY = "parent_email"
private const val PIN_HASH_KEY = "parent_pin_hash"
private const val LEGACY_PIN_KEY = "parent_pin"
private const val LAST_TICK_KEY = "last_tick_elapsed_ms"
private const val HEARTBEAT_KEY = "service_heartbeat_ms"
private const val MAX_FAILED_ATTEMPTS = 50

private fun Context.guardPrefs(): SharedPreferences =
    getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
private fun timestamp(): String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())

private fun hashPin(pin: String): String {
    val bytes = MessageDigest.getInstance("SHA-256").digest("KidsMonnter:$pin".toByteArray())
    return bytes.joinToString("") { "%02x".format(it) }
}

private fun hasStoredPin(prefs: SharedPreferences): Boolean =
    prefs.getString(PIN_HASH_KEY, "").orEmpty().isNotBlank() ||
        prefs.getString(LEGACY_PIN_KEY, "").orEmpty().length == 6

private fun verifyPin(prefs: SharedPreferences, candidate: String): Boolean {
    if (candidate.length != 6 || candidate.any { !it.isDigit() }) return false
    val storedHash = prefs.getString(PIN_HASH_KEY, "").orEmpty()
    if (storedHash.isNotBlank()) return storedHash == hashPin(candidate)

    val legacy = prefs.getString(LEGACY_PIN_KEY, "").orEmpty()
    if (legacy == candidate) {
        prefs.edit().putString(PIN_HASH_KEY, hashPin(candidate)).remove(LEGACY_PIN_KEY).commit()
        return true
    }
    return false
}

private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}

private fun Context.deviceAdminComponent() =
    ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)

private fun Context.configureDeviceOwnerPolicies() {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return
    try {
        val admin = deviceAdminComponent()
        manager.setLockTaskPackages(admin, arrayOf(packageName))
        manager.setUninstallBlocked(admin, packageName, true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) manager.setStatusBarDisabled(admin, true)
    } catch (_: SecurityException) {
        // Device-owner policies vary by vendor. Protection continues without kiosk hardening.
    }
}

private fun readFailedAttempts(prefs: SharedPreferences): List<Map<String, String>> =
    prefs.getString(FAILED_ATTEMPTS_KEY, "").orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .mapNotNull { line ->
            val parts = line.split("|", limit = 2)
            if (parts.size == 2) mapOf("time" to parts[0], "source" to parts[1]) else null
        }
        .toList()
        .asReversed()

private fun createChannel(context: Context, id: String, name: String, importance: Int) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(id, name, importance).apply { setShowBadge(false) })
    }
}

private fun showSecurityAlert(context: Context, prefs: SharedPreferences, source: String) {
    createChannel(context, ALERT_CHANNEL_ID, "تنبيهات محاولات تجاوز القفل", NotificationManager.IMPORTANCE_HIGH)
    val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    val notification = NotificationCompat.Builder(context, ALERT_CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_dialog_alert)
        .setContentTitle("محاولة PIN غير صحيحة")
        .setContentText(source)
        .setStyle(NotificationCompat.BigTextStyle().bigText("تم تسجيل محاولة فاشلة: $source"))
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .setAutoCancel(true)
        .build()
    manager.notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notification)
}

private fun recordFailedAttempt(context: Context, prefs: SharedPreferences, source: String) {
    val entries = prefs.getString(FAILED_ATTEMPTS_KEY, "").orEmpty()
        .lineSequence().filter { it.isNotBlank() }.toMutableList()
    entries.add("${timestamp()}|$source")
    prefs.edit().putString(FAILED_ATTEMPTS_KEY, entries.takeLast(MAX_FAILED_ATTEMPTS).joinToString("\n")).apply()
    showSecurityAlert(context, prefs, source)
}

class MainActivity : FlutterActivity() {
    private val channelName = "kidsmonnter/control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).setMethodCallHandler { call, result ->
            val prefs = guardPrefs()
            when (call.method) {
                "setPin" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (pin.length != 6 || pin.any { !it.isDigit() }) {
                        result.error("INVALID_PIN", "PIN must be 6 digits", null)
                    } else {
                        prefs.edit().putString(PIN_HASH_KEY, hashPin(pin)).remove(LEGACY_PIN_KEY).commit()
                        result.success(true)
                    }
                }
                "hasPin" -> result.success(hasStoredPin(prefs))
                "verifyPin" -> {
                    val valid = verifyPin(prefs, call.argument<String>("pin").orEmpty())
                    if (!valid) recordFailedAttempt(this, prefs, "تأكيد إعدادات ولي الأمر")
                    result.success(valid)
                }
                "setParentEmail" -> {
                    val email = call.argument<String>("email")?.trim().orEmpty()
                    if (email.isNotEmpty() && !android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
                        result.error("INVALID_EMAIL", "عنوان البريد الإلكتروني غير صحيح", null)
                    } else {
                        prefs.edit().putString(PARENT_EMAIL_KEY, email).apply()
                        result.success(true)
                    }
                }
                "sendSecurityReport" -> {
                    val email = prefs.getString(PARENT_EMAIL_KEY, "").orEmpty()
                    if (email.isBlank()) {
                        result.error("NO_EMAIL", "لم يتم تحديد بريد ولي الأمر", null)
                    } else {
                        val body = buildString {
                            appendLine("تقرير حارس وقت الأطفال")
                            appendLine("تاريخ التقرير: ${timestamp()}")
                            readFailedAttempts(prefs).forEachIndexed { index, item ->
                                appendLine("${index + 1}. ${item["time"]} - ${item["source"]}")
                            }
                        }
                        try {
                            startActivity(Intent(Intent.ACTION_SENDTO).apply {
                                data = Uri.parse("mailto:")
                                putExtra(Intent.EXTRA_EMAIL, arrayOf(email))
                                putExtra(Intent.EXTRA_SUBJECT, "تقرير محاولات PIN")
                                putExtra(Intent.EXTRA_TEXT, body)
                            })
                            result.success(true)
                        } catch (_: ActivityNotFoundException) {
                            result.error("NO_MAIL_APP", "لا يوجد تطبيق بريد إلكتروني مثبت", null)
                        }
                    }
                }
                "startProtection" -> {
                    val minutes = (call.argument<Int>("minutes") ?: 60).coerceIn(1, 1440)
                    prefs.edit()
                        .putInt("daily_minutes", minutes)
                        .putBoolean("enabled", true)
                        .putString("date", today())
                        .remove("unlocked_date")
                        .remove(LAST_TICK_KEY)
                        .commit()
                    startMonitorServiceSafely()
                    result.success(true)
                }
                "stopProtection" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "إيقاف الحماية")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        prefs.edit().putBoolean("enabled", false).remove(LAST_TICK_KEY).commit()
                        stopService(Intent(this, MonitorService::class.java))
                        result.success(true)
                    }
                }
                "addTime" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    val minutes = (call.argument<Int>("minutes") ?: 0).coerceAtLeast(0)
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "إضافة وقت")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        val used = prefs.getInt("used_seconds", 0)
                        prefs.edit().putInt("used_seconds", (used - minutes * 60).coerceAtLeast(0))
                            .remove("unlocked_date").apply()
                        result.success(true)
                    }
                }
                "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                "getStatus" -> result.success(mapOf(
                    "enabled" to prefs.getBoolean("enabled", false),
                    "usedSeconds" to prefs.getInt("used_seconds", 0),
                    "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                    "hasPin" to hasStoredPin(prefs),
                    "failedAttempts" to readFailedAttempts(prefs).size,
                    "parentEmail" to prefs.getString(PARENT_EMAIL_KEY, "").orEmpty(),
                    "overlayAllowed" to Settings.canDrawOverlays(this),
                    "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L)
                ))
                "openOverlaySettings" -> {
                    startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
                    result.success(true)
                }
                "canDrawOverlays" -> result.success(Settings.canDrawOverlays(this))
                "getDevicePolicyStatus" -> {
                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = deviceAdminComponent()
                    val deviceOwner = dpm.isDeviceOwnerApp(packageName)
                    val uninstallBlocked = if (deviceOwner) {
                        try {
                            dpm.isUninstallBlocked(admin, packageName)
                        } catch (_: SecurityException) {
                            false
                        }
                    } else {
                        false
                    }
                    result.success(mapOf(
                        "deviceOwner" to deviceOwner,
                        "adminActive" to dpm.isAdminActive(admin),
                        "lockTaskPermitted" to dpm.isLockTaskPermitted(packageName),
                        "uninstallBlocked" to uninstallBlocked
                    ))
                }
                "configureDeviceOwner" -> {
                    configureDeviceOwnerPolicies()
                    result.success(true)
                }
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
                Intent.ACTION_SCREEN_OFF -> {
                    accountElapsedUsage()
                    screenOn = false
                    resetClockAnchor()
                }
                Intent.ACTION_SCREEN_ON, Intent.ACTION_USER_PRESENT -> {
                    screenOn = true
                    resetClockAnchor()
                    enforceLockIfNeeded()
                }
            }
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            resetIfNewDay()
            prefs.edit().putLong(HEARTBEAT_KEY, System.currentTimeMillis()).apply()
            if (prefs.getBoolean("enabled", false)) {
                monitorOverlayPermission()
                accountElapsedUsage()
                enforceLockIfNeeded()
            } else {
                resetClockAnchor()
            }
            handler.postDelayed(this, 1000L)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
        screenOn = (getSystemService(POWER_SERVICE) as PowerManager).isInteractive
        @Suppress("DEPRECATION")
        registerReceiver(screenReceiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_USER_PRESENT)
        })
        resetClockAnchor()
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        handler.post(ticker)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        resetClockAnchor()
        enforceLockIfNeeded()
        return START_STICKY
    }

    override fun onBind(intent: Intent?) = null

    override fun onTaskRemoved(rootIntent: Intent?) {
        scheduleRestart()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        accountElapsedUsage()
        handler.removeCallbacks(ticker)
        try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
        if (prefs.getBoolean("enabled", false)) scheduleRestart()
        super.onDestroy()
    }

    private fun scheduleRestart() {
        if (!prefs.getBoolean("enabled", false)) return
        val pending = PendingIntent.getService(
            this, 991, Intent(this, MonitorService::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        (getSystemService(ALARM_SERVICE) as AlarmManager).setAndAllowWhileIdle(
            AlarmManager.ELAPSED_REALTIME_WAKEUP,
            SystemClock.elapsedRealtime() + 2000L,
            pending
        )
    }

    private fun resetClockAnchor() {
        prefs.edit().putLong(LAST_TICK_KEY, SystemClock.elapsedRealtime()).apply()
    }

    private fun accountElapsedUsage() {
        val now = SystemClock.elapsedRealtime()
        val previousAnchor = prefs.getLong(LAST_TICK_KEY, now)
        prefs.edit().putLong(LAST_TICK_KEY, now).apply()

        if (!screenOn || !prefs.getBoolean("enabled", false)) return
        if (prefs.getString("unlocked_date", "") == today()) return
        if (previousAnchor <= 0L || previousAnchor > now) return

        val elapsedSeconds = ((now - previousAnchor) / 1000L).toInt().coerceIn(0, 300)
        if (elapsedSeconds <= 0) return

        val limit = prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
        val before = prefs.getInt("used_seconds", 0).coerceAtLeast(0)
        val after = (before + elapsedSeconds).coerceAtMost(limit)
        if (after != before) prefs.edit().putInt("used_seconds", after).apply()

        if (before < limit - 300 && after >= limit - 300) notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
        if (before < limit - 60 && after >= limit - 60) notifyWarning("تبقّت دقيقة واحدة من وقت الهاتف")
    }

    private fun resetIfNewDay() {
        val currentDate = today()
        if (prefs.getString("date", "") == currentDate) return
        prefs.edit().putString("date", currentDate).putInt("used_seconds", 0)
            .remove("unlocked_date").remove(LAST_TICK_KEY).commit()
        overlayWarningRecorded = false
        resetClockAnchor()
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
            startActivity(Intent(this, LockActivity::class.java).addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS
            ))
        } catch (_: Exception) {
            notifyWarning("انتهى وقت الهاتف، لكن تعذر فتح شاشة القفل")
        }
    }

    private fun monitorOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            if (!overlayWarningRecorded) {
                overlayWarningRecorded = true
                recordFailedAttempt(this, prefs, "تم إلغاء صلاحية شاشة القفل")
            }
        } else overlayWarningRecorded = false
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
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
}

class LockActivity : Activity() {
    private val prefs by lazy { guardPrefs() }
    private val handler = Handler(Looper.getMainLooper())
    private var authorizedExit = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configureDeviceOwnerPolicies()
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
        )
        if (!shouldRemainLocked()) { finish(); return }
        showImmersive()
        val dpm = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        if (dpm.isLockTaskPermitted(packageName)) try { startLockTask() } catch (_: Exception) {}
        setContentView(buildLockView())
    }

    override fun onResume() {
        super.onResume()
        showImmersive()
        if (!shouldRemainLocked()) exitLock()
    }

    override fun onPause() {
        super.onPause()
        if (!authorizedExit && shouldRemainLocked()) handler.postDelayed({
            try {
                startActivity(Intent(this, LockActivity::class.java).addFlags(
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP
                ))
            } catch (_: Exception) {}
        }, 300L)
    }

    private fun shouldRemainLocked(): Boolean {
        if (!prefs.getBoolean("enabled", false)) return false
        if (prefs.getString("unlocked_date", "") == today()) return false
        return prefs.getInt("used_seconds", 0) >= prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
    }

    private fun showImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
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
                if (verifyForLock(pinInput.text.toString(), "فتح القفل وإضافة 15 دقيقة", status)) {
                    val used = prefs.getInt("used_seconds", 0)
                    prefs.edit().putInt("used_seconds", (used - 900).coerceAtLeast(0)).apply()
                    exitLock()
                }
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        root.addView(Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            setOnClickListener {
                if (verifyForLock(pinInput.text.toString(), "فتح الهاتف لبقية اليوم", status)) {
                    prefs.edit().putString("unlocked_date", today()).apply()
                    exitLock()
                }
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
        return root
    }

    private fun verifyForLock(pin: String, source: String, status: TextView): Boolean {
        val valid = verifyPin(prefs, pin)
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
        if (prefs.getBoolean("enabled", false)) context.startMonitorServiceSafely()
    }
}
