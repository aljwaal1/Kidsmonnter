package com.explapp.kidstimeguard

import android.app.*
import android.content.*
import android.graphics.Color
import android.os.*
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
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
private const val MAX_FAILED_ATTEMPTS = 50

class MainActivity : FlutterActivity() {
    private val channel = "kidsmonnter/control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            when (call.method) {
                "setPin" -> {
                    val pin = call.argument<String>("pin") ?: ""
                    if (pin.length != 6 || pin.any { !it.isDigit() }) {
                        result.error("INVALID_PIN", "PIN must be 6 digits", null)
                    } else {
                        prefs.edit().putString("parent_pin", pin).apply()
                        result.success(true)
                    }
                }
                "hasPin" -> result.success((prefs.getString("parent_pin", "") ?: "").length == 6)
                "verifyPin" -> {
                    val pin = call.argument<String>("pin") ?: ""
                    val valid = pin == prefs.getString("parent_pin", "")
                    if (!valid) recordFailedAttempt(prefs, "تغيير المدة")
                    result.success(valid)
                }
                "startProtection" -> {
                    val minutes = call.argument<Int>("minutes") ?: 60
                    prefs.edit()
                        .putInt("daily_minutes", minutes)
                        .putBoolean("enabled", true)
                        .putString("date", today())
                        .apply()
                    startMonitorService(this)
                    result.success(true)
                }
                "stopProtection" -> {
                    val pin = call.argument<String>("pin") ?: ""
                    if (pin != prefs.getString("parent_pin", "")) {
                        recordFailedAttempt(prefs, "إيقاف الحماية")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        prefs.edit().putBoolean("enabled", false).apply()
                        stopService(Intent(this, MonitorService::class.java))
                        result.success(true)
                    }
                }
                "addTime" -> {
                    val pin = call.argument<String>("pin") ?: ""
                    val minutes = call.argument<Int>("minutes") ?: 0
                    if (pin != prefs.getString("parent_pin", "")) {
                        recordFailedAttempt(prefs, "إضافة وقت")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        val used = prefs.getInt("used_seconds", 0)
                        prefs.edit().putInt("used_seconds", (used - minutes * 60).coerceAtLeast(0)).apply()
                        result.success(true)
                    }
                }
                "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                "clearFailedAttempts" -> {
                    val pin = call.argument<String>("pin") ?: ""
                    if (pin != prefs.getString("parent_pin", "")) {
                        recordFailedAttempt(prefs, "مسح سجل المحاولات")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        prefs.edit().remove(FAILED_ATTEMPTS_KEY).apply()
                        result.success(true)
                    }
                }
                "getStatus" -> result.success(mapOf(
                    "enabled" to prefs.getBoolean("enabled", false),
                    "usedSeconds" to prefs.getInt("used_seconds", 0),
                    "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                    "hasPin" to ((prefs.getString("parent_pin", "") ?: "").length == 6),
                    "failedAttempts" to readFailedAttempts(prefs).size
                ))
                "openOverlaySettings" -> {
                    startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, android.net.Uri.parse("package:$packageName")))
                    result.success(true)
                }
                "canDrawOverlays" -> result.success(Settings.canDrawOverlays(this))
                else -> result.notImplemented()
            }
        }
    }
}

private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())

private fun attemptTimestamp(): String =
    SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())

private fun recordFailedAttempt(prefs: android.content.SharedPreferences, source: String) {
    val entries = prefs.getString(FAILED_ATTEMPTS_KEY, "")
        .orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .toMutableList()
    entries.add("${attemptTimestamp()}|$source")
    val trimmed = entries.takeLast(MAX_FAILED_ATTEMPTS)
    prefs.edit().putString(FAILED_ATTEMPTS_KEY, trimmed.joinToString("\n")).apply()
}

private fun readFailedAttempts(prefs: android.content.SharedPreferences): List<Map<String, String>> =
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

private fun startMonitorService(context: Context) {
    val intent = Intent(context, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent)
    else context.startService(intent)
}

class MonitorService : Service() {
    private val prefs by lazy { getSharedPreferences(PREFS_NAME, MODE_PRIVATE) }
    private var screenOn = true
    private val handler = Handler(Looper.getMainLooper())
    private var lockShown = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            screenOn = intent?.action == Intent.ACTION_SCREEN_ON
            if (intent?.action == Intent.ACTION_SCREEN_OFF) lockShown = false
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            resetIfNewDay()
            if (prefs.getBoolean("enabled", false) && screenOn) {
                val used = prefs.getInt("used_seconds", 0) + 1
                prefs.edit().putInt("used_seconds", used).apply()
                val limit = prefs.getInt("daily_minutes", 60) * 60
                if (used == (limit - 300).coerceAtLeast(1)) notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
                if (used == (limit - 60).coerceAtLeast(1)) notifyWarning("تبقّت دقيقة واحدة من وقت الهاتف")
                if (used >= limit && !lockShown) {
                    lockShown = true
                    showLock()
                }
            }
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        screenOn = (getSystemService(POWER_SERVICE) as PowerManager).isInteractive
        registerReceiver(screenReceiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
        })
        startForeground(1001, buildNotification("الحماية تعمل الآن"))
        handler.post(ticker)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY
    override fun onBind(intent: Intent?) = null

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
        super.onDestroy()
    }

    private fun resetIfNewDay() {
        val value = today()
        if (prefs.getString("date", "") != value) {
            prefs.edit().putString("date", value).putInt("used_seconds", 0).apply()
            lockShown = false
        }
    }

    private fun showLock() {
        if (!Settings.canDrawOverlays(this)) return
        startActivity(Intent(this, LockActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        })
    }

    private fun notifyWarning(text: String) {
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(1002, buildNotification(text))
    }

    private fun buildNotification(text: String): Notification = NotificationCompat.Builder(this, "kidsmonnter_guard")
        .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
        .setContentTitle("حارس وقت الأطفال")
        .setContentText(text)
        .setOngoing(true)
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .build()

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel("kidsmonnter_guard", "حماية وقت الهاتف", NotificationManager.IMPORTANCE_HIGH)
            )
        }
    }
}

class LockActivity : Activity() {
    private val prefs by lazy { getSharedPreferences(PREFS_NAME, MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)
        showLockUi()
    }

    private fun showLockUi() {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
            setBackgroundColor(Color.rgb(25, 42, 39))
        }
        val title = TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        val body = TextView(this).apply {
            text = "أدخل رمز ولي الأمر لإضافة وقت أو فتح الهاتف."
            textSize = 17f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 24, 0, 28)
        }
        val pin = EditText(this).apply {
            hint = "PIN من 6 أرقام"
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            gravity = Gravity.CENTER
            maxEms = 6
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }
        val error = TextView(this).apply {
            setTextColor(Color.rgb(255, 150, 150))
            gravity = Gravity.CENTER
            setPadding(0, 12, 0, 12)
        }
        val add15 = Button(this).apply {
            text = "إضافة 15 دقيقة"
            setOnClickListener {
                if (pin.text.toString() == prefs.getString("parent_pin", "")) {
                    val used = prefs.getInt("used_seconds", 0)
                    prefs.edit().putInt("used_seconds", (used - 900).coerceAtLeast(0)).apply()
                    finish()
                } else {
                    recordFailedAttempt(prefs, "شاشة القفل: إضافة وقت")
                    error.text = "رمز غير صحيح"
                    pin.text.clear()
                }
            }
        }
        val unlockToday = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            setOnClickListener {
                if (pin.text.toString() == prefs.getString("parent_pin", "")) {
                    prefs.edit().putBoolean("enabled", false).apply()
                    stopService(Intent(this@LockActivity, MonitorService::class.java))
                    finish()
                } else {
                    recordFailedAttempt(prefs, "شاشة القفل: فتح الهاتف")
                    error.text = "رمز غير صحيح"
                    pin.text.clear()
                }
            }
        }
        layout.addView(title)
        layout.addView(body)
        layout.addView(pin)
        layout.addView(error)
        layout.addView(add15)
        layout.addView(unlockToday)
        setContentView(layout)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {}
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        if (prefs.getBoolean("enabled", false)) startMonitorService(context)
    }
}
