package com.explapp.kidstimeguard

import android.app.*
import android.content.*
import android.os.*
import android.provider.Settings
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private fun todayKey(): String =
    SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())

private fun Context.startMonitorService() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        startForegroundService(intent)
    } else {
        startService(intent)
    }
}

class MainActivity : FlutterActivity() {
    private val channel = "kidsmonnter/control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "startProtection" -> {
                        val minutes = call.argument<Int>("minutes") ?: 60
                        getSharedPreferences("kidsmonnter", MODE_PRIVATE).edit()
                            .putInt("daily_minutes", minutes)
                            .putBoolean("enabled", true)
                            .putString("date", todayKey())
                            .apply()
                        startMonitorService()
                        result.success(true)
                    }
                    "stopProtection" -> {
                        getSharedPreferences("kidsmonnter", MODE_PRIVATE).edit()
                            .putBoolean("enabled", false)
                            .apply()
                        stopService(Intent(this, MonitorService::class.java))
                        result.success(true)
                    }
                    "getStatus" -> {
                        val prefs = getSharedPreferences("kidsmonnter", MODE_PRIVATE)
                        result.success(
                            mapOf(
                                "enabled" to prefs.getBoolean("enabled", false),
                                "usedSeconds" to prefs.getInt("used_seconds", 0),
                                "dailyMinutes" to prefs.getInt("daily_minutes", 60)
                            )
                        )
                    }
                    "openOverlaySettings" -> {
                        startActivity(
                            Intent(
                                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                android.net.Uri.parse("package:$packageName")
                            )
                        )
                        result.success(true)
                    }
                    "canDrawOverlays" -> result.success(Settings.canDrawOverlays(this))
                    else -> result.notImplemented()
                }
            }
    }
}

class MonitorService : Service() {
    private val prefs by lazy { getSharedPreferences("kidsmonnter", MODE_PRIVATE) }
    private var screenOn = true
    private val handler = Handler(Looper.getMainLooper())
    private var lockShown = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_ON -> screenOn = true
                Intent.ACTION_SCREEN_OFF -> screenOn = false
            }
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            resetIfNewDay()
            if (prefs.getBoolean("enabled", false) && screenOn) {
                val used = prefs.getInt("used_seconds", 0) + 1
                prefs.edit().putInt("used_seconds", used).apply()
                val limit = prefs.getInt("daily_minutes", 60) * 60

                if (used == (limit - 300).coerceAtLeast(1)) {
                    notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
                }
                if (used == (limit - 60).coerceAtLeast(1)) {
                    notifyWarning("تبقّت دقيقة واحدة من وقت الهاتف")
                }
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
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
        }
        registerReceiver(screenReceiver, filter)
        startForeground(1001, buildNotification("الحماية تعمل الآن"))
        handler.post(ticker)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onBind(intent: Intent?) = null

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        unregisterReceiver(screenReceiver)
        super.onDestroy()
    }

    private fun resetIfNewDay() {
        val today = todayKey()
        if (prefs.getString("date", "") != today) {
            prefs.edit()
                .putString("date", today)
                .putInt("used_seconds", 0)
                .apply()
            lockShown = false
        }
    }

    private fun showLock() {
        if (!Settings.canDrawOverlays(this)) return
        val intent = Intent(this, LockActivity::class.java).apply {
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
        }
        startActivity(intent)
    }

    private fun notifyWarning(text: String) {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(1002, buildNotification(text))
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, "kidsmonnter_guard")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("حارس وقت الأطفال")
            .setContentText(text)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(
                NotificationChannel(
                    "kidsmonnter_guard",
                    "حماية وقت الهاتف",
                    NotificationManager.IMPORTANCE_HIGH
                )
            )
        }
    }
}

class LockActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
        )

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setPadding(48, 48, 48, 48)
            setBackgroundColor(android.graphics.Color.rgb(25, 42, 39))
        }
        val title = android.widget.TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(android.graphics.Color.WHITE)
            gravity = android.view.Gravity.CENTER
        }
        val body = android.widget.TextView(this).apply {
            text = "سيعود الهاتف للعمل تلقائيًا في اليوم التالي."
            textSize = 18f
            setTextColor(android.graphics.Color.LTGRAY)
            gravity = android.view.Gravity.CENTER
            setPadding(0, 28, 0, 0)
        }
        layout.addView(title)
        layout.addView(body)
        setContentView(layout)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() = Unit
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.getSharedPreferences("kidsmonnter", Context.MODE_PRIVATE)
        if (prefs.getBoolean("enabled", false)) {
            context.startMonitorService()
        }
    }
}
