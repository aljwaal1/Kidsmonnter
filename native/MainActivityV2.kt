package com.explapp.kidstimeguard

import android.Manifest
import android.app.*
import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.*
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Rect
import android.net.Uri
import android.os.*
import android.provider.Settings
import android.util.Log
import android.text.InputType
import android.view.Gravity
import android.view.KeyEvent
import android.view.WindowInsets
import android.view.WindowInsetsController
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
import java.io.File

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
private const val MONITOR_WATCHDOG_ACTION = "com.explapp.kidstimeguard.RESTART_MONITOR"
private const val WATCHDOG_REQUEST_CODE = 991
private const val WATCHDOG_INTERVAL_MS = 60_000L
private const val STALE_HEARTBEAT_MS = 30_000L
private const val LAST_SERVICE_START_REQUEST_ELAPSED_KEY = "last_service_start_request_elapsed_ms"
private const val SERVICE_START_REQUEST_COOLDOWN_MS = 15_000L
private const val MAX_FAILED_ATTEMPTS = 50
private const val LOCK_LAUNCH_COOLDOWN_MS = 5_000L
private const val DIAGNOSTIC_LOG_FILE = "kidsmonnter-diagnostic.log"
private const val MAX_DIAGNOSTIC_LOG_BYTES = 512 * 1024
private const val DIAGNOSTIC_HEARTBEAT_INTERVAL_MS = 15_000L
private const val BOOT_PREFS_NAME = "kidsmonnter_boot"
private const val BOOT_ENABLED_KEY = "protection_enabled"
private const val BOOT_RETRY_ACTION = "com.explapp.kidstimeguard.BOOT_RETRY"
private const val BOOT_RETRY_REQUEST_BASE = 1200
private const val WAKE_LOCK_TIMEOUT_MS = 12_000L
private const val LOCK_ACTIVITY_LAUNCH_COOLDOWN_MS = 2_000L
private const val LOCK_ACTION_GRACE_MS = 3_000L
private const val PIN_FAILURE_STREAK_KEY = "lock_pin_failure_streak"
private const val PIN_BLOCK_UNTIL_MS_KEY = "lock_pin_block_until_ms"
private const val MAX_PIN_BLOCK_MS = 60_000L

private fun Context.guardPrefs(): SharedPreferences =
    getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

// STRICT_RUNTIME_RESILIENCE_MARKER
private fun Context.bootPrefs(): SharedPreferences =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
        createDeviceProtectedStorageContext()
            .getSharedPreferences(BOOT_PREFS_NAME, Context.MODE_PRIVATE)
    } else {
        getSharedPreferences(BOOT_PREFS_NAME, Context.MODE_PRIVATE)
    }

private fun Context.syncBootProtectionState(enabled: Boolean) {
    bootPrefs().edit().putBoolean(BOOT_ENABLED_KEY, enabled).commit()
}

private fun Context.isProtectionEnabledForBoot(): Boolean {
    if (bootPrefs().getBoolean(BOOT_ENABLED_KEY, false)) return true
    val unlocked = Build.VERSION.SDK_INT < Build.VERSION_CODES.N ||
        (getSystemService(Context.USER_SERVICE) as UserManager).isUserUnlocked
    return unlocked && guardPrefs().getBoolean("enabled", false)
}

private fun Context.isIgnoringBatteryOptimizations(): Boolean =
    (getSystemService(Context.POWER_SERVICE) as PowerManager)
        .isIgnoringBatteryOptimizations(packageName)

private fun Context.canUseExactWatchdog(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
        (getSystemService(Context.ALARM_SERVICE) as AlarmManager).canScheduleExactAlarms()

private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
private fun timestamp(): String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())

// RUNTIME_DIAGNOSTICS_MARKER: persistent runtime logging for background-service failures.
private fun Context.appendGuardLog(event: String, details: String = "", error: Throwable? = null) {
    val normalizedDetails = details.replace("\n", " ").replace("\r", " ").take(1600)
    val line = buildString {
        append(timestamp())
        append(" | uptime=")
        append(SystemClock.elapsedRealtime())
        append(" | pid=")
        append(Process.myPid())
        append(" | ")
        append(event)
        if (normalizedDetails.isNotBlank()) {
            append(" | ")
            append(normalizedDetails)
        }
        if (error != null) {
            append(" | ")
            append(error.javaClass.simpleName)
            append(": ")
            append(error.message.orEmpty().replace("\n", " ").take(800))
        }
    }

    if (error == null) Log.i("KidsMonnterGuard", line) else Log.e("KidsMonnterGuard", line, error)

    try {
        val file = File(filesDir, DIAGNOSTIC_LOG_FILE)
        if (file.exists() && file.length() > MAX_DIAGNOSTIC_LOG_BYTES.toLong()) {
            val tail = file.readText().takeLast(MAX_DIAGNOSTIC_LOG_BYTES / 2)
            file.writeText("${timestamp()} | LOG_ROTATED | retained newest entries\n$tail")
        }
        file.appendText(line + "\n")
    } catch (loggingError: Exception) {
        Log.e("KidsMonnterGuard", "Unable to persist diagnostic log", loggingError)
    }
}

private fun Context.readGuardLog(): String {
    val prefs = guardPrefs()
    val snapshot = buildString {
        appendLine("KidsMonnter diagnostic snapshot")
        appendLine("generated=${timestamp()}")
        appendLine("enabled=${prefs.getBoolean("enabled", false)}")
        appendLine("date=${prefs.getString("date", "")}")
        appendLine("usedSeconds=${prefs.getInt("used_seconds", 0)}")
        appendLine("dailyMinutes=${prefs.getInt("daily_minutes", 60)}")
        appendLine("heartbeatMs=${prefs.getLong(HEARTBEAT_KEY, 0L)}")
        appendLine("lastTickElapsedMs=${prefs.getLong(LAST_TICK_KEY, 0L)}")
        appendLine("overlayAllowed=${Settings.canDrawOverlays(this@readGuardLog)}")
        appendLine("sdk=${Build.VERSION.SDK_INT}")
        appendLine("manufacturer=${Build.MANUFACTURER}")
        appendLine("model=${Build.MODEL}")
        appendLine("----------------------------------------")
    }
    val file = File(filesDir, DIAGNOSTIC_LOG_FILE)
    return snapshot + if (file.exists()) file.readText() else "No runtime entries yet."
}

private fun Context.clearGuardLog() {
    try {
        File(filesDir, DIAGNOSTIC_LOG_FILE).delete()
    } catch (error: Exception) {
        Log.e("KidsMonnterGuard", "Unable to clear diagnostic log", error)
    }
}

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

// EXTREME_LOCK_HARDENING_MARKER
private fun lockPinBlockRemainingMs(prefs: SharedPreferences): Long {
    val until = prefs.getLong(PIN_BLOCK_UNTIL_MS_KEY, 0L)
    if (until <= 0L) return 0L
    val remaining = until - System.currentTimeMillis()
    if (remaining <= 0L || remaining > MAX_PIN_BLOCK_MS) {
        prefs.edit().remove(PIN_BLOCK_UNTIL_MS_KEY).apply()
        return 0L
    }
    return remaining
}

private fun registerLockPinFailure(
    context: Context,
    prefs: SharedPreferences,
    source: String,
): Long {
    val streak = (prefs.getInt(PIN_FAILURE_STREAK_KEY, 0) + 1).coerceAtMost(50)
    val delayMs = when {
        streak >= 10 -> 60_000L
        streak >= 5 -> 15_000L
        else -> 2_000L
    }
    prefs.edit()
        .putInt(PIN_FAILURE_STREAK_KEY, streak)
        .putLong(PIN_BLOCK_UNTIL_MS_KEY, System.currentTimeMillis() + delayMs)
        .commit()
    recordFailedAttempt(context, prefs, "$source (محاولة متتالية $streak)")
    return delayMs
}

private fun clearLockPinFailureState(prefs: SharedPreferences) {
    prefs.edit()
        .remove(PIN_FAILURE_STREAK_KEY)
        .remove(PIN_BLOCK_UNTIL_MS_KEY)
        .apply()
}

private fun lockDelayText(delayMs: Long): String =
    "انتظر ${((delayMs + 999L) / 1000L).coerceAtLeast(1L)} ثانية ثم حاول مرة أخرى."

private fun Context.disableProtectionFailOpen(reason: String) {
    val prefs = guardPrefs()
    prefs.edit()
        .putBoolean("enabled", false)
        .remove(LAST_TICK_KEY)
        .remove("unlocked_date")
        .commit()
    syncBootProtectionState(false)
    clearLockPinFailureState(prefs)
    releaseDeviceOwnerPolicies()
    appendGuardLog("LOCK_FAIL_OPEN", "reason=$reason")
}

private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    appendGuardLog("SERVICE_START_REQUEST", "sdk=${Build.VERSION.SDK_INT}")
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
    } catch (error: Exception) {
        appendGuardLog("SERVICE_START_REQUEST_FAILED", error = error)
        throw error
    }
}

private fun Activity.requestNotificationPermissionIfNeeded() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
    ) {
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7001)
    }
}

private fun Context.guardNotificationContentIntent(): PendingIntent =
    PendingIntent.getActivity(
        this,
        1003,
        Intent(this, MainActivity::class.java).addFlags(
            Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        ),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
    )

private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = System.currentTimeMillis()
    val age = now - heartbeat
    return age > 30_000L || age < -5_000L
}

private fun Context.requestMonitorServiceStartIfAllowed(
    prefs: SharedPreferences,
    force: Boolean = false,
): Boolean {
    val now = SystemClock.elapsedRealtime()
    val lastRequest = prefs.getLong(LAST_SERVICE_START_REQUEST_ELAPSED_KEY, 0L)
    val requestIsRecent = lastRequest > 0L && now >= lastRequest &&
        now - lastRequest < SERVICE_START_REQUEST_COOLDOWN_MS
    if (!force && requestIsRecent) return false

    prefs.edit().putLong(LAST_SERVICE_START_REQUEST_ELAPSED_KEY, now).apply()
    startMonitorServiceSafely()
    return true
}

private fun Context.scheduleMonitorWatchdog(delayMs: Long = WATCHDOG_INTERVAL_MS) {
    val pending = PendingIntent.getBroadcast(
        this,
        WATCHDOG_REQUEST_CODE,
        Intent(this, BootReceiver::class.java).setAction(MONITOR_WATCHDOG_ACTION),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )
    val alarm = getSystemService(Context.ALARM_SERVICE) as AlarmManager
    val triggerAt = SystemClock.elapsedRealtime() + delayMs
    if (canUseExactWatchdog()) {
        alarm.setExactAndAllowWhileIdle(
            AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending,
        )
        appendGuardLog("WATCHDOG_SCHEDULED", "mode=exact delayMs=$delayMs")
    } else {
        alarm.setAndAllowWhileIdle(
            AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending,
        )
        appendGuardLog(
            "WATCHDOG_SCHEDULED",
            "mode=inexact delayMs=$delayMs exactPermission=false",
        )
    }
}

private fun Context.scheduleBootRetries() {
    val alarm = getSystemService(Context.ALARM_SERVICE) as AlarmManager
    listOf(15_000L, 60_000L, 5 * 60_000L).forEachIndexed { index, delay ->
        val pending = PendingIntent.getBroadcast(
            this,
            BOOT_RETRY_REQUEST_BASE + index,
            Intent(this, BootReceiver::class.java)
                .setAction(BOOT_RETRY_ACTION)
                .putExtra("retry_index", index),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val triggerAt = SystemClock.elapsedRealtime() + delay
        if (canUseExactWatchdog()) {
            alarm.setExactAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending,
            )
        } else {
            alarm.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending,
            )
        }
    }
    appendGuardLog(
        "BOOT_RETRIES_SCHEDULED",
        "delays=15s,60s,300s exact=${canUseExactWatchdog()}",
    )
}

private fun Context.deviceAdminComponent() =
    ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)

// PARENT_PIN_UNINSTALL_PROTECTION_MARKER
private fun Context.ensureUninstallProtection(): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return false
    return try {
        manager.setUninstallBlocked(deviceAdminComponent(), packageName, true)
        appendGuardLog("UNINSTALL_PROTECTION_ENFORCED", "deviceOwner=true")
        true
    } catch (error: SecurityException) {
        appendGuardLog("UNINSTALL_PROTECTION_ENFORCE_FAILED", error = error)
        false
    }
}

private fun Context.configureDeviceOwnerPolicies(): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return false
    return try {
        val admin = deviceAdminComponent()
        manager.setLockTaskPackages(admin, arrayOf(packageName))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            manager.setLockTaskFeatures(admin, DevicePolicyManager.LOCK_TASK_FEATURE_NONE)
        }
        manager.setUninstallBlocked(admin, packageName, true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, true)
        }
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_APPLIED")
        true
    } catch (error: SecurityException) {
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_FAILED", error = error)
        false
    }
}

private fun Context.releaseDeviceOwnerPolicies() {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return
    try {
        val admin = deviceAdminComponent()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setLockTaskPackages(admin, emptyArray<String>())
        // إيقاف حماية الوقت لا يسمح بحذف التطبيق. يبقى الحذف محمياً برمز الأب.
        manager.setUninstallBlocked(admin, packageName, true)
        appendGuardLog("RUNTIME_POLICIES_RELEASED_UNINSTALL_STILL_BLOCKED")
    } catch (error: SecurityException) {
        appendGuardLog("RUNTIME_POLICY_RELEASE_FAILED", error = error)
    }
}

private fun Activity.openSelfUninstallScreen() {
    startActivity(
        Intent(Intent.ACTION_DELETE, Uri.parse("package:$packageName")).addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP,
        ),
    )
    appendGuardLog("SYSTEM_UNINSTALL_SCREEN_OPENED")
}

private fun Activity.prepareParentAuthorizedUninstall(prefs: SharedPreferences): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    val admin = deviceAdminComponent()
    if (!manager.isDeviceOwnerApp(packageName)) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_REJECTED", "reason=device_owner_required")
        return false
    }

    return try {
        prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .remove("unlocked_date")
            .commit()
        syncBootProtectionState(false)
        stopService(Intent(this, MonitorService::class.java))

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setLockTaskPackages(admin, emptyArray<String>())
        manager.setUninstallBlocked(admin, packageName, false)
        appendGuardLog("UNINSTALL_AUTHORIZED_BY_PARENT_PIN", "deviceOwner=true")

        @Suppress("DEPRECATION")
        manager.clearDeviceOwnerApp(packageName)
        appendGuardLog("DEVICE_OWNER_CLEARED_FOR_UNINSTALL")
        true
    } catch (error: Exception) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_FAILED", error = error)
        false
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
        appendGuardLog("APP_ENGINE_READY", "activity=${javaClass.simpleName}")
        ensureUninstallProtection()
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
                    syncBootProtectionState(true)
                    ensureUninstallProtection()
                    appendGuardLog("PROTECTION_ENABLED", "minutes=$minutes used=${prefs.getInt("used_seconds", 0)}")
                    requestNotificationPermissionIfNeeded()
                    startMonitorServiceSafely()
                    result.success(true)
                }
                "restartProtectionService" -> {
                    if (!prefs.getBoolean("enabled", false)) {
                        result.error("PROTECTION_DISABLED", "الحماية غير مفعلة", null)
                    } else {
                        appendGuardLog("MANUAL_SERVICE_RESTART", "requestedFromUi=true")
                        startMonitorServiceSafely()
                        result.success(true)
                    }
                }
                "stopProtection" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "إيقاف الحماية")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        prefs.edit().putBoolean("enabled", false).remove(LAST_TICK_KEY).commit()
                        syncBootProtectionState(false)
                        appendGuardLog("PROTECTION_DISABLED", "source=main_activity")
                        releaseDeviceOwnerPolicies()
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
                        appendGuardLog("TIME_ADDED", "minutes=$minutes before=$used after=${prefs.getInt("used_seconds", 0)}")
                        result.success(true)
                    }
                }
                "getDiagnosticLog" -> {
                    appendGuardLog("DIAGNOSTIC_LOG_VIEWED")
                    result.success(readGuardLog())
                }
                "clearDiagnosticLog" -> {
                    clearGuardLog()
                    appendGuardLog("DIAGNOSTIC_LOG_CLEARED")
                    result.success(true)
                }
                "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                // RUNTIME_DIAGNOSTICS_CONTRACT_COMPAT_MARKER
                "openExactAlarmSettings" -> {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        startActivity(
                            Intent(
                                Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                                Uri.parse("package:$packageName"),
                            ),
                        )
                    }
                    result.success(true)
                }
                "openBatteryOptimizationSettings" -> {
                    try {
                        startActivity(
                            Intent(
                                Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                                Uri.parse("package:$packageName"),
                            ),
                        )
                    } catch (_: Exception) {
                        startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                    }
                    result.success(true)
                }
                // STRICT_RUNTIME_CONTRACT_COMPAT_MARKER
                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) requestMonitorServiceStartIfAllowed(prefs).also {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                    }
                    result.success(mapOf(
                        "enabled" to prefs.getBoolean("enabled", false),
                        "usedSeconds" to prefs.getInt("used_seconds", 0),
                        "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                        "hasPin" to hasStoredPin(prefs),
                        "failedAttempts" to readFailedAttempts(prefs).size,
                        "parentEmail" to prefs.getString(PARENT_EMAIL_KEY, "").orEmpty(),
                        "overlayAllowed" to Settings.canDrawOverlays(this),
                        "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L),
                        "exactAlarmAllowed" to canUseExactWatchdog(),
                        "batteryOptimizationIgnored" to isIgnoringBatteryOptimizations()
                    ))
                }
                "openOverlaySettings" -> {
                    startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
                    result.success(true)
                }
                "canDrawOverlays" -> result.success(Settings.canDrawOverlays(this))
                "authorizeUninstall" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "محاولة السماح بحذف التطبيق")
                        appendGuardLog("UNINSTALL_PIN_REJECTED")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                        if (!manager.isDeviceOwnerApp(packageName)) {
                            result.error(
                                "DEVICE_OWNER_REQUIRED",
                                "منع الحذف الكامل يحتاج تفعيل Device Owner أولاً",
                                null,
                            )
                        } else if (!prepareParentAuthorizedUninstall(prefs)) {
                            result.error(
                                "UNINSTALL_PREPARE_FAILED",
                                "تعذر إلغاء حماية الحذف بصورة آمنة",
                                null,
                            )
                        } else {
                            result.success(true)
                            Handler(Looper.getMainLooper()).postDelayed({
                                try {
                                    openSelfUninstallScreen()
                                } catch (error: Exception) {
                                    appendGuardLog("SYSTEM_UNINSTALL_SCREEN_FAILED", error = error)
                                }
                            }, 350L)
                        }
                    }
                }
                "getDevicePolicyStatus" -> {
                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = deviceAdminComponent()
                    val deviceOwner = dpm.isDeviceOwnerApp(packageName)
                    if (deviceOwner) ensureUninstallProtection()
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
    private var lastLockLaunchElapsedMs = 0L
    private var lockOverlayView: View? = null
    private var lockWindowManager: WindowManager? = null
    private val lockOverlayPin = StringBuilder(6)
    private var lockOverlayPinDisplay: TextView? = null
    private var lockOverlayStatus: TextView? = null
    private var lockOverlayActionButtons: List<Button> = emptyList()
    private var lastDiagnosticHeartbeatElapsedMs = 0L
    private var lastLockActivityLaunchElapsedMs = 0L
    private var lockActionInProgress = false
    private var lockActionGraceUntilElapsedMs = 0L

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            try {
                appendGuardLog("SCREEN_EVENT", "action=${intent?.action.orEmpty()} screenOnBefore=$screenOn")
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
            } catch (error: Exception) {
                appendGuardLog("SCREEN_EVENT_ERROR", "action=${intent?.action.orEmpty()}", error)
            }
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            try {
                resetIfNewDay()
                prefs.edit()
                    .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
                    .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)
                    .apply()
                if (prefs.getBoolean("enabled", false)) {
                    monitorOverlayPermission()
                    accountElapsedUsage()
                    enforceLockIfNeeded()
                } else {
                    resetClockAnchor()
                }

                val nowElapsed = SystemClock.elapsedRealtime()
                if (nowElapsed - lastDiagnosticHeartbeatElapsedMs >= DIAGNOSTIC_HEARTBEAT_INTERVAL_MS) {
                    lastDiagnosticHeartbeatElapsedMs = nowElapsed
                    appendGuardLog(
                        "SERVICE_HEARTBEAT",
                        "enabled=${prefs.getBoolean("enabled", false)} screenOn=$screenOn used=${prefs.getInt("used_seconds", 0)} limit=${prefs.getInt("daily_minutes", 60) * 60} overlay=${Settings.canDrawOverlays(this@MonitorService)} lockVisible=${lockOverlayView != null}",
                    )
                }
            } catch (error: Exception) {
                appendGuardLog("TICK_ERROR", "screenOn=$screenOn", error)
            } finally {
                handler.postDelayed(this, 1000L)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        appendGuardLog("SERVICE_CREATED", "enabled=${prefs.getBoolean("enabled", false)}")
        screenOn = (getSystemService(POWER_SERVICE) as PowerManager).isInteractive
        @Suppress("DEPRECATION")
        registerReceiver(screenReceiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_USER_PRESENT)
        })
        resetClockAnchor()
        scheduleMonitorWatchdog()
        handler.post(ticker)
        appendGuardLog("SERVICE_FOREGROUND_READY", "screenOn=$screenOn")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        appendGuardLog("SERVICE_START_COMMAND", "action=${intent?.action.orEmpty()} flags=$flags startId=$startId")
        try {
            resetClockAnchor()
            appendGuardLog(
                "LOCK_EVALUATION",
                "used=${prefs.getInt("used_seconds", 0)} limit=${prefs.getInt("daily_minutes", 60) * 60} finished=${isTimeFinished()} screenOn=$screenOn",
            )
            enforceLockIfNeeded()
        } catch (error: Exception) {
            appendGuardLog("SERVICE_START_COMMAND_ERROR", error = error)
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?) = null

    override fun onTaskRemoved(rootIntent: Intent?) {
        appendGuardLog("SERVICE_TASK_REMOVED", "enabled=${prefs.getBoolean("enabled", false)}")
        scheduleRestart()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        appendGuardLog("SERVICE_DESTROYED", "enabled=${prefs.getBoolean("enabled", false)}")
        try {
            accountElapsedUsage()
            dismissLockOverlay()
        } catch (error: Exception) {
            appendGuardLog("SERVICE_DESTROY_CLEANUP_ERROR", error = error)
        } finally {
            handler.removeCallbacks(ticker)
            try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
            if (prefs.getBoolean("enabled", false)) scheduleRestart()
            super.onDestroy()
        }
    }

    private fun scheduleRestart() {
        if (!prefs.getBoolean("enabled", false)) return
        scheduleMonitorWatchdog(2_000L)
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
        if (after != before) {
            prefs.edit().putInt("used_seconds", after).apply()
            if (after == limit || after % 15 == 0) {
                appendGuardLog("USAGE_ACCOUNTED", "before=$before after=$after elapsed=$elapsedSeconds limit=$limit")
            }
        }

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

    // BACKGROUND_LOCK_OVERLAY_MARKER: the service owns the lock UI so Android does not
    // need to start an Activity while the application is in the background.
    private fun enforceLockIfNeeded() {
        if (!prefs.getBoolean("enabled", false)) {
            dismissLockOverlay()
            return
        }
        if (!hasStoredPin(prefs)) {
            appendGuardLog("LOCK_ABORTED_INVALID_PIN_STATE")
            disableProtectionFailOpen("missing_or_corrupt_parent_pin")
            dismissLockOverlay()
            stopSelf()
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (!isTimeFinished()) {
            if (!lockActionInProgress && now >= lockActionGraceUntilElapsedMs) {
                dismissLockOverlay()
            }
            return
        }
        if (lockActionInProgress || now < lockActionGraceUntilElapsedMs) return

        appendGuardLog(
            "LOCK_TRIGGERED",
            "used=${prefs.getInt("used_seconds", 0)} limit=${prefs.getInt("daily_minutes", 60) * 60} sdk=${Build.VERSION.SDK_INT}",
        )
        showLock()
        if (screenOn) launchLockActivityReliably()
    }

    // SDK27_RELIABLE_LOCK_MARKER
    private fun launchLockActivityReliably() {
        val policy = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val deviceOwner = policy.isDeviceOwnerApp(packageName)
        val legacyBackgroundLaunchAllowed = Build.VERSION.SDK_INT <= Build.VERSION_CODES.P
        if (!deviceOwner && !legacyBackgroundLaunchAllowed) {
            appendGuardLog(
                "LOCK_ACTIVITY_SKIPPED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=false overlayFallback=true",
            )
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (now - lastLockActivityLaunchElapsedMs < LOCK_ACTIVITY_LAUNCH_COOLDOWN_MS) return
        lastLockActivityLaunchElapsedMs = now
        try {
            if (deviceOwner) configureDeviceOwnerPolicies()
            startActivity(
                Intent(this, LockActivity::class.java).addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or
                        Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS or
                        Intent.FLAG_ACTIVITY_NO_ANIMATION,
                ),
            )
            appendGuardLog(
                "LOCK_ACTIVITY_STARTED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=$deviceOwner legacy=$legacyBackgroundLaunchAllowed",
            )
        } catch (error: Exception) {
            appendGuardLog(
                "LOCK_ACTIVITY_START_FAILED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=$deviceOwner",
                error,
            )
            showLock()
        }
    }

    private fun showLock() {
        if (lockOverlayView != null) return
        if (!Settings.canDrawOverlays(this)) {
            appendGuardLog("LOCK_BLOCKED_NO_OVERLAY_PERMISSION")
            notifyWarning("انتهى وقت الهاتف. فعّل صلاحية الظهور فوق التطبيقات ليعمل القفل تلقائياً")
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (now - lastLockLaunchElapsedMs < LOCK_LAUNCH_COOLDOWN_MS) return
        lastLockLaunchElapsedMs = now
        appendGuardLog("LOCK_CREATE_ATTEMPT", "used=${prefs.getInt("used_seconds", 0)} limit=${prefs.getInt("daily_minutes", 60) * 60}")

        try {
            configureDeviceOwnerPolicies()
            val manager = getSystemService(WINDOW_SERVICE) as WindowManager
            val view = buildBackgroundLockOverlay().apply {
                systemUiVisibility = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                    View.SYSTEM_UI_FLAG_FULLSCREEN or
                    View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                    View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                    View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                isFocusable = true
                isFocusableInTouchMode = true
                setOnKeyListener { _, keyCode, _ ->
                    keyCode == KeyEvent.KEYCODE_BACK ||
                        keyCode == KeyEvent.KEYCODE_MENU ||
                        keyCode == KeyEvent.KEYCODE_SEARCH ||
                        keyCode == KeyEvent.KEYCODE_ASSIST ||
                        keyCode == KeyEvent.KEYCODE_APP_SWITCH
                }
            }
            val overlayType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            }
            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                overlayType,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_FULLSCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_SECURE or
                    WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM,
                PixelFormat.OPAQUE,
            ).apply {
                gravity = Gravity.TOP or Gravity.START
                softInputMode = WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    layoutInDisplayCutoutMode =
                        WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
                }
            }
            manager.addView(view, params)
            lockWindowManager = manager
            lockOverlayView = view
            view.post {
                view.requestFocus()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && view.width > 0 && view.height > 0) {
                    view.systemGestureExclusionRects = listOf(Rect(0, 0, view.width, view.height))
                }
            }
            refreshBackgroundLockPinUi()
            appendGuardLog("LOCK_CREATED", "overlayType=$overlayType")
        } catch (error: Exception) {
            appendGuardLog("LOCK_CREATE_FAILED", error = error)
            dismissLockOverlay()
            notifyWarning("انتهى وقت الهاتف، لكن تعذر إنشاء شاشة القفل التلقائية")
        }
    }

    private fun buildBackgroundLockOverlay(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(32, 32, 32, 32)
            setBackgroundColor(Color.rgb(25, 42, 39))
            isClickable = true
            isFocusable = true
            isFocusableInTouchMode = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }
        root.addView(TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(-1, -2))
        root.addView(TextView(this).apply {
            text = "أدخل رمز ولي الأمر من لوحة الأرقام الآمنة."
            textSize = 17f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 16, 0, 20)
        }, LinearLayout.LayoutParams(-1, -2))

        lockOverlayPinDisplay = TextView(this).apply {
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(12, 18, 12, 18)
            setBackgroundColor(Color.rgb(38, 62, 58))
            contentDescription = "رمز ولي الأمر، ست خانات"
        }
        root.addView(lockOverlayPinDisplay, LinearLayout.LayoutParams(-1, -2))

        lockOverlayStatus = TextView(this).apply {
            setTextColor(Color.rgb(255, 180, 170))
            gravity = Gravity.CENTER
            setPadding(0, 10, 0, 10)
        }
        root.addView(lockOverlayStatus, LinearLayout.LayoutParams(-1, -2))

        val keypad = GridLayout(this).apply {
            columnCount = 3
            rowCount = 4
            useDefaultMargins = true
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "مسح", "0", "⌫").forEach { label ->
            keypad.addView(Button(this).apply {
                text = label
                textSize = if (label.length == 1) 22f else 16f
                minHeight = 64
                setOnClickListener {
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        lockOverlayStatus?.text = lockDelayText(remaining)
                        return@setOnClickListener
                    }
                    when (label) {
                        "مسح" -> lockOverlayPin.clear()
                        "⌫" -> if (lockOverlayPin.isNotEmpty()) {
                            lockOverlayPin.deleteCharAt(lockOverlayPin.length - 1)
                        }
                        else -> if (lockOverlayPin.length < 6) lockOverlayPin.append(label)
                    }
                    lockOverlayStatus?.text = ""
                    refreshBackgroundLockPinUi()
                }
            }, GridLayout.LayoutParams().apply {
                width = 0
                height = GridLayout.LayoutParams.WRAP_CONTENT
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
            })
        }
        root.addView(keypad, LinearLayout.LayoutParams(-1, -2))

        val addTime = Button(this).apply {
            text = "إضافة 15 دقيقة"
            setOnClickListener { addTimeFromBackgroundLock() }
        }
        val unlockToday = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            setOnClickListener { unlockTodayFromBackgroundLock() }
        }
        val stopProtection = Button(this).apply {
            text = "إيقاف الحماية"
            setOnClickListener { stopProtectionFromBackgroundLock() }
        }
        lockOverlayActionButtons = listOf(addTime, unlockToday, stopProtection)
        root.addView(addTime, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })
        root.addView(unlockToday, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
        root.addView(stopProtection, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        return ScrollView(this).apply {
            isFillViewport = true
            addView(root, FrameLayout.LayoutParams(-1, -2))
        }
    }

    private fun refreshBackgroundLockPinUi() {
        val dots = MutableList(6) { index -> if (index < lockOverlayPin.length) "●" else "○" }
        lockOverlayPinDisplay?.text = dots.joinToString(" ")
        val ready = lockOverlayPin.length == 6
        lockOverlayActionButtons.forEach { it.isEnabled = ready }
    }

    private fun verifyBackgroundLockPin(source: String): Boolean {
        val remaining = lockPinBlockRemainingMs(prefs)
        if (remaining > 0L) {
            lockOverlayStatus?.text = lockDelayText(remaining)
            return false
        }
        if (verifyPin(prefs, lockOverlayPin.toString())) {
            clearLockPinFailureState(prefs)
            return true
        }
        val delay = registerLockPinFailure(this, prefs, source)
        lockOverlayStatus?.text = "رمز ولي الأمر غير صحيح. ${lockDelayText(delay)}"
        lockOverlayPin.clear()
        refreshBackgroundLockPinUi()
        return false
    }

    private fun completeAuthorizedOverlayAction() {
        lockActionGraceUntilElapsedMs = SystemClock.elapsedRealtime() + LOCK_ACTION_GRACE_MS
        dismissLockOverlay()
        lockActionInProgress = false
    }

    private fun addTimeFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح القفل وإضافة 15 دقيقة")) return
        lockActionInProgress = true
        val used = prefs.getInt("used_seconds", 0)
        val saved = prefs.edit()
            .putInt("used_seconds", (used - 900).coerceAtLeast(0))
            .remove("unlocked_date")
            .commit()
        if (!saved) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر حفظ الوقت الإضافي. حاول مرة أخرى."
            return
        }
        resetClockAnchor()
        completeAuthorizedOverlayAction()
    }

    private fun unlockTodayFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح الهاتف لبقية اليوم")) return
        lockActionInProgress = true
        if (!prefs.edit().putString("unlocked_date", today()).commit()) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر حفظ أمر الفتح. حاول مرة أخرى."
            return
        }
        completeAuthorizedOverlayAction()
    }

    private fun stopProtectionFromBackgroundLock() {
        if (!verifyBackgroundLockPin("إيقاف الحماية من شاشة القفل")) return
        lockActionInProgress = true
        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }
        clearLockPinFailureState(prefs)
        syncBootProtectionState(false)
        releaseDeviceOwnerPolicies()
        dismissLockOverlay()
        stopSelf()
    }

    private fun dismissLockOverlay() {
        val view = lockOverlayView
        val manager = lockWindowManager
        lockOverlayView = null
        lockWindowManager = null
        lockOverlayPinDisplay = null
        lockOverlayStatus = null
        lockOverlayActionButtons = emptyList()
        lockOverlayPin.clear()
        if (view != null) {
            try {
                (manager ?: getSystemService(WINDOW_SERVICE) as WindowManager)
                    .removeViewImmediate(view)
            } catch (error: Exception) {
                appendGuardLog("LOCK_OVERLAY_REMOVE_FAILED", error = error)
            }
        }
    }

    private fun monitorOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            if (!overlayWarningRecorded) {
                overlayWarningRecorded = true
                appendGuardLog("OVERLAY_PERMISSION_MISSING")
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
            .setContentIntent(guardNotificationContentIntent())
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
    private val enteredPin = StringBuilder(6)
    private lateinit var pinDisplay: TextView
    private lateinit var statusView: TextView
    private lateinit var addTimeButton: Button
    private lateinit var unlockTodayButton: Button
    private lateinit var stopProtectionButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configureDeviceOwnerPolicies()
        window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)
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
            if (!authorizedExit && shouldRemainLocked() && isScreenInteractive()) {
                try {
                    startActivity(Intent(this, LockActivity::class.java).addFlags(
                        Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP
                    ))
                } catch (_: Exception) {}
            }
        }, 800L)
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun isScreenInteractive(): Boolean =
        (getSystemService(POWER_SERVICE) as PowerManager).isInteractive

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
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(32, 32, 32, 32)
            setBackgroundColor(Color.rgb(25, 42, 39))
        }
        root.addView(TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(-1, -2))
        root.addView(TextView(this).apply {
            text = "أدخل رمز ولي الأمر من لوحة الأرقام الآمنة."
            textSize = 17f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 16, 0, 20)
        }, LinearLayout.LayoutParams(-1, -2))

        pinDisplay = TextView(this).apply {
            text = "○ ○ ○ ○ ○ ○"
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(12, 18, 12, 18)
            setBackgroundColor(Color.rgb(38, 62, 58))
            contentDescription = "رمز ولي الأمر، ست خانات"
        }
        root.addView(pinDisplay, LinearLayout.LayoutParams(-1, -2))

        statusView = TextView(this).apply {
            setTextColor(Color.rgb(255, 180, 170))
            gravity = Gravity.CENTER
            setPadding(0, 10, 0, 10)
        }
        root.addView(statusView, LinearLayout.LayoutParams(-1, -2))

        val keypad = GridLayout(this).apply {
            columnCount = 3
            rowCount = 4
            useDefaultMargins = true
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "مسح", "0", "⌫").forEach { label ->
            keypad.addView(Button(this).apply {
                text = label
                textSize = if (label.length == 1) 22f else 16f
                minHeight = 64
                setOnClickListener {
                    when (label) {
                        "مسح" -> enteredPin.clear()
                        "⌫" -> if (enteredPin.isNotEmpty()) enteredPin.deleteCharAt(enteredPin.lastIndex)
                        else -> if (enteredPin.length < 6) enteredPin.append(label)
                    }
                    statusView.text = ""
                    refreshPinUi()
                }
            }, GridLayout.LayoutParams().apply {
                width = 0
                height = GridLayout.LayoutParams.WRAP_CONTENT
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
            })
        }
        root.addView(keypad, LinearLayout.LayoutParams(-1, -2))

        addTimeButton = Button(this).apply {
            text = "إضافة 15 دقيقة"
            isEnabled = false
            setOnClickListener { unlockWithPin(addTime = true) }
        }
        root.addView(addTimeButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })

        unlockTodayButton = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            isEnabled = false
            setOnClickListener { unlockWithPin(addTime = false) }
        }
        root.addView(unlockTodayButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        stopProtectionButton = Button(this).apply {
            text = "إيقاف الحماية"
            isEnabled = false
            setOnClickListener { disableProtectionWithPin() }
        }
        root.addView(stopProtectionButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(root, FrameLayout.LayoutParams(-1, -2))
        }
        refreshPinUi()
        return scroll
    }

    private fun refreshPinUi() {
        val dots = MutableList(6) { index -> if (index < enteredPin.length) "●" else "○" }
        pinDisplay.text = dots.joinToString(" ")
        val ready = enteredPin.length == 6
        addTimeButton.isEnabled = ready
        unlockTodayButton.isEnabled = ready
        stopProtectionButton.isEnabled = ready
    }

    private fun disableProtectionWithPin() {
        val pin = enteredPin.toString()
        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, "إيقاف الحماية من شاشة القفل")
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
            enteredPin.clear()
            refreshPinUi()
            return
        }

        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            statusView.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }

        releaseDeviceOwnerPolicies()
        stopService(Intent(this, MonitorService::class.java))
        exitLock()
    }

    private fun unlockWithPin(addTime: Boolean) {
        val pin = enteredPin.toString()
        val source = if (addTime) "فتح القفل وإضافة 15 دقيقة" else "فتح الهاتف لبقية اليوم"
        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, source)
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
            enteredPin.clear()
            refreshPinUi()
            return
        }

        val saved = if (addTime) {
            val used = prefs.getInt("used_seconds", 0)
            prefs.edit().putInt("used_seconds", (used - 900).coerceAtLeast(0)).commit()
        } else {
            prefs.edit().putString("unlocked_date", today()).commit()
        }
        if (!saved) {
            statusView.text = "تعذر حفظ أمر الفتح. حاول مرة أخرى."
            return
        }
        exitLock()
    }

    private fun exitLock() {
        authorizedExit = true
        handler.removeCallbacksAndMessages(null)
        try { stopLockTask() } catch (_: Exception) {}
        finishAndRemoveTask()
        overridePendingTransition(0, 0)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() = Unit
}

class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action.orEmpty()
        val pendingResult = goAsync()
        val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val wakeLock = power.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "KidsMonnter:boot-recovery",
        )
        try {
            wakeLock.acquire(WAKE_LOCK_TIMEOUT_MS)
            val userUnlocked = Build.VERSION.SDK_INT < Build.VERSION_CODES.N ||
                (context.getSystemService(Context.USER_SERVICE) as UserManager).isUserUnlocked
            val enabled = context.isProtectionEnabledForBoot()
            context.appendGuardLog(
                "BOOT_RECEIVER",
                "action=$action enabled=$enabled userUnlocked=$userUnlocked",
            )
            if (!enabled) return
            if (!userUnlocked) {
                context.scheduleBootRetries()
                return
            }

            val prefs = context.guardPrefs()
            context.syncBootProtectionState(prefs.getBoolean("enabled", enabled))
            val isWatchdog = action == MONITOR_WATCHDOG_ACTION || action == BOOT_RETRY_ACTION
            val heartbeatAge = System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)
            val serviceNeedsRestart =
                !isWatchdog || heartbeatAge < 0L || heartbeatAge > STALE_HEARTBEAT_MS
            context.appendGuardLog(
                "WATCHDOG_DECISION",
                "action=$action isWatchdog=$isWatchdog heartbeatAge=$heartbeatAge " +
                    "restart=$serviceNeedsRestart exact=${context.canUseExactWatchdog()}",
            )

            try {
                if (serviceNeedsRestart) {
                    context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)
                }
            } catch (error: Exception) {
                context.appendGuardLog("BOOT_SERVICE_START_FAILED", "action=$action", error)
                context.scheduleBootRetries()
            }
            context.scheduleMonitorWatchdog()
            if (action == Intent.ACTION_BOOT_COMPLETED ||
                action == Intent.ACTION_MY_PACKAGE_REPLACED
            ) {
                context.scheduleBootRetries()
            }
        } catch (error: Exception) {
            context.appendGuardLog("BOOT_RECEIVER_ERROR", "action=$action", error)
        } finally {
            if (wakeLock.isHeld) wakeLock.release()
            pendingResult.finish()
        }
    }
}
