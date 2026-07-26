from pathlib import Path

NATIVE_PATH = Path("native/MainActivityV2.kt")
DART_PATH = Path("lib/main.dart")
NATIVE_MARKER = "RUNTIME_DIAGNOSTICS_MARKER"
DART_MARKER = "RUNTIME_DIAGNOSTICS_UI_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: لم يتم العثور على المقطع المتوقع")
    return text.replace(old, new, 1)


native = NATIVE_PATH.read_text(encoding="utf-8")
if NATIVE_MARKER not in native:
    native = replace_once(
        native,
        "import android.provider.Settings\n",
        "import android.provider.Settings\nimport android.util.Log\n",
        "استيراد سجل Android",
    )
    native = replace_once(
        native,
        "import java.util.*\n",
        "import java.util.*\nimport java.io.File\n",
        "استيراد ملف السجل",
    )
    native = replace_once(
        native,
        "private const val LOCK_LAUNCH_COOLDOWN_MS = 5_000L\n",
        "private const val LOCK_LAUNCH_COOLDOWN_MS = 5_000L\n"
        "private const val DIAGNOSTIC_LOG_FILE = \"kidsmonnter-diagnostic.log\"\n"
        "private const val MAX_DIAGNOSTIC_LOG_BYTES = 512 * 1024\n"
        "private const val DIAGNOSTIC_HEARTBEAT_INTERVAL_MS = 15_000L\n",
        "ثوابت سجل التشخيص",
    )
    native = replace_once(
        native,
        'private fun timestamp(): String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())\n',
        '''private fun timestamp(): String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())

// RUNTIME_DIAGNOSTICS_MARKER: persistent runtime logging for background-service failures.
private fun Context.appendGuardLog(event: String, details: String = "", error: Throwable? = null) {
    val normalizedDetails = details.replace("\\n", " ").replace("\\r", " ").take(1600)
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
            append(error.message.orEmpty().replace("\\n", " ").take(800))
        }
    }

    if (error == null) Log.i("KidsMonnterGuard", line) else Log.e("KidsMonnterGuard", line, error)

    try {
        val file = File(filesDir, DIAGNOSTIC_LOG_FILE)
        if (file.exists() && file.length() > MAX_DIAGNOSTIC_LOG_BYTES.toLong()) {
            val tail = file.readText().takeLast(MAX_DIAGNOSTIC_LOG_BYTES / 2)
            file.writeText("${timestamp()} | LOG_ROTATED | retained newest entries\\n$tail")
        }
        file.appendText(line + "\\n")
    } catch (loggingError: Exception) {
        Log.e("KidsMonnterGuard", "Unable to persist diagnostic log", loggingError)
    }
}

private fun Context.readGuardLog(): String {
    val prefs = guardPrefs()
    val snapshot = buildString {
        appendLine("KidsMonnter diagnostic snapshot")
        appendLine("generated=${timestamp()}")
        appendLine("enabled=${prefs.getBoolean(\"enabled\", false)}")
        appendLine("date=${prefs.getString(\"date\", \"\")}")
        appendLine("usedSeconds=${prefs.getInt(\"used_seconds\", 0)}")
        appendLine("dailyMinutes=${prefs.getInt(\"daily_minutes\", 60)}")
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
''',
        "دوال سجل التشخيص",
    )
    native = replace_once(
        native,
        '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}
''',
        '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    appendGuardLog("SERVICE_START_REQUEST", "sdk=${Build.VERSION.SDK_INT}")
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
    } catch (error: Exception) {
        appendGuardLog("SERVICE_START_REQUEST_FAILED", error = error)
        throw error
    }
}
''',
        "تشخيص طلب تشغيل الخدمة",
    )
    native = replace_once(
        native,
        '''    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
''',
        '''    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        appendGuardLog("APP_ENGINE_READY", "activity=${javaClass.simpleName}")
''',
        "تشخيص فتح التطبيق",
    )
    native = replace_once(
        native,
        '''                    requestNotificationPermissionIfNeeded()
                    startMonitorServiceSafely()
                    result.success(true)
''',
        '''                    appendGuardLog("PROTECTION_ENABLED", "minutes=$minutes used=${prefs.getInt(\"used_seconds\", 0)}")
                    requestNotificationPermissionIfNeeded()
                    startMonitorServiceSafely()
                    result.success(true)
''',
        "تشخيص تفعيل الحماية",
    )
    native = replace_once(
        native,
        '''                    } else {
                        startMonitorServiceSafely()
                        result.success(true)
                    }
                }
                "stopProtection" -> {
''',
        '''                    } else {
                        appendGuardLog("MANUAL_SERVICE_RESTART", "requestedFromUi=true")
                        startMonitorServiceSafely()
                        result.success(true)
                    }
                }
                "stopProtection" -> {
''',
        "تشخيص إعادة تشغيل الخدمة يدويًا",
    )
    native = replace_once(
        native,
        '''                        releaseDeviceOwnerPolicies()
                        stopService(Intent(this, MonitorService::class.java))
                        result.success(true)
''',
        '''                        appendGuardLog("PROTECTION_DISABLED", "source=main_activity")
                        releaseDeviceOwnerPolicies()
                        stopService(Intent(this, MonitorService::class.java))
                        result.success(true)
''',
        "تشخيص إيقاف الحماية",
    )
    native = replace_once(
        native,
        '''                        prefs.edit().putInt("used_seconds", (used - minutes * 60).coerceAtLeast(0))
                            .remove("unlocked_date").apply()
                        result.success(true)
''',
        '''                        prefs.edit().putInt("used_seconds", (used - minutes * 60).coerceAtLeast(0))
                            .remove("unlocked_date").apply()
                        appendGuardLog("TIME_ADDED", "minutes=$minutes before=$used after=${prefs.getInt(\"used_seconds\", 0)}")
                        result.success(true)
''',
        "تشخيص إضافة الوقت",
    )
    native = replace_once(
        native,
        '''                "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) requestMonitorServiceStartIfAllowed(prefs)
''',
        '''                "getDiagnosticLog" -> {
                    appendGuardLog("DIAGNOSTIC_LOG_VIEWED")
                    result.success(readGuardLog())
                }
                "clearDiagnosticLog" -> {
                    clearGuardLog()
                    appendGuardLog("DIAGNOSTIC_LOG_CLEARED")
                    result.success(true)
                }
                "getFailedAttempts" -> result.success(readFailedAttempts(prefs))
                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)}")
                        requestMonitorServiceStartIfAllowed(prefs)
                    }
''',
        "قنوات عرض ومسح سجل التشخيص",
    )
    native = replace_once(
        native,
        '''    private var lockOverlayStatus: TextView? = null
    private var lockOverlayActionButtons: List<Button> = emptyList()
''',
        '''    private var lockOverlayStatus: TextView? = null
    private var lockOverlayActionButtons: List<Button> = emptyList()
    private var lastDiagnosticHeartbeatElapsedMs = 0L
''',
        "حالة نبضة سجل التشخيص",
    )
    native = replace_once(
        native,
        '''    private val screenReceiver = object : BroadcastReceiver() {
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
''',
        '''    private val screenReceiver = object : BroadcastReceiver() {
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
''',
        "حماية وتشخيص مستقبل الشاشة",
    )
    native = replace_once(
        native,
        '''    private val ticker = object : Runnable {
        override fun run() {
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
            handler.postDelayed(this, 1000L)
        }
    }
''',
        '''    private val ticker = object : Runnable {
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
                        "enabled=${prefs.getBoolean(\"enabled\", false)} screenOn=$screenOn used=${prefs.getInt(\"used_seconds\", 0)} limit=${prefs.getInt(\"daily_minutes\", 60) * 60} overlay=${Settings.canDrawOverlays(this@MonitorService)} lockVisible=${lockOverlayView != null}",
                    )
                }
            } catch (error: Exception) {
                appendGuardLog("TICK_ERROR", "screenOn=$screenOn", error)
            } finally {
                handler.postDelayed(this, 1000L)
            }
        }
    }
''',
        "حماية دورة العداد وتسجيل نبضتها",
    )
    native = replace_once(
        native,
        '''    override fun onCreate() {
        super.onCreate()
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
''',
        '''    override fun onCreate() {
        super.onCreate()
        appendGuardLog("SERVICE_CREATED", "enabled=${prefs.getBoolean(\"enabled\", false)}")
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
''',
        "تشخيص إنشاء الخدمة",
    )
    native = replace_once(
        native,
        '''        scheduleMonitorWatchdog()
        handler.post(ticker)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        resetClockAnchor()
        enforceLockIfNeeded()
        return START_STICKY
    }
''',
        '''        scheduleMonitorWatchdog()
        handler.post(ticker)
        appendGuardLog("SERVICE_FOREGROUND_READY", "screenOn=$screenOn")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        appendGuardLog("SERVICE_START_COMMAND", "action=${intent?.action.orEmpty()} flags=$flags startId=$startId")
        return try {
            resetClockAnchor()
            enforceLockIfNeeded()
            START_STICKY
        } catch (error: Exception) {
            appendGuardLog("SERVICE_START_COMMAND_ERROR", error = error)
            START_STICKY
        }
    }
''',
        "تشخيص بدء الخدمة",
    )
    native = replace_once(
        native,
        '''    override fun onTaskRemoved(rootIntent: Intent?) {
        scheduleRestart()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        accountElapsedUsage()
''',
        '''    override fun onTaskRemoved(rootIntent: Intent?) {
        appendGuardLog("SERVICE_TASK_REMOVED", "enabled=${prefs.getBoolean(\"enabled\", false)}")
        scheduleRestart()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        appendGuardLog("SERVICE_DESTROYED", "enabled=${prefs.getBoolean(\"enabled\", false)}")
        accountElapsedUsage()
''',
        "تشخيص إزالة التطبيق وتدمير الخدمة",
    )
    native = replace_once(
        native,
        '''        if (after != before) prefs.edit().putInt("used_seconds", after).apply()

        if (before < limit - 300 && after >= limit - 300) notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
''',
        '''        if (after != before) {
            prefs.edit().putInt("used_seconds", after).apply()
            if (after == limit || after % 15 == 0) {
                appendGuardLog("USAGE_ACCOUNTED", "before=$before after=$after elapsed=$elapsedSeconds limit=$limit")
            }
        }

        if (before < limit - 300 && after >= limit - 300) notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
''',
        "تشخيص احتساب وقت الاستخدام",
    )
    native = replace_once(
        native,
        '''        if (!Settings.canDrawOverlays(this)) {
            notifyWarning("انتهى وقت الهاتف. فعّل صلاحية الظهور فوق التطبيقات ليعمل القفل تلقائياً")
            return
        }
''',
        '''        if (!Settings.canDrawOverlays(this)) {
            appendGuardLog("LOCK_BLOCKED_NO_OVERLAY_PERMISSION")
            notifyWarning("انتهى وقت الهاتف. فعّل صلاحية الظهور فوق التطبيقات ليعمل القفل تلقائياً")
            return
        }
''',
        "تشخيص غياب صلاحية القفل",
    )
    native = replace_once(
        native,
        '''        lastLockLaunchElapsedMs = now

        try {
            configureDeviceOwnerPolicies()
''',
        '''        lastLockLaunchElapsedMs = now
        appendGuardLog("LOCK_CREATE_ATTEMPT", "used=${prefs.getInt(\"used_seconds\", 0)} limit=${prefs.getInt(\"daily_minutes\", 60) * 60}")

        try {
            configureDeviceOwnerPolicies()
''',
        "تشخيص محاولة إنشاء القفل",
    )
    native = replace_once(
        native,
        '''            lockWindowManager = manager
            lockOverlayView = view
            refreshBackgroundLockPinUi()
        } catch (_: Exception) {
            dismissLockOverlay()
            notifyWarning("انتهى وقت الهاتف، لكن تعذر إنشاء شاشة القفل التلقائية")
        }
''',
        '''            lockWindowManager = manager
            lockOverlayView = view
            refreshBackgroundLockPinUi()
            appendGuardLog("LOCK_CREATED", "overlayType=$overlayType")
        } catch (error: Exception) {
            appendGuardLog("LOCK_CREATE_FAILED", error = error)
            dismissLockOverlay()
            notifyWarning("انتهى وقت الهاتف، لكن تعذر إنشاء شاشة القفل التلقائية")
        }
''',
        "تشخيص نتيجة إنشاء القفل",
    )
    native = replace_once(
        native,
        '''            if (!overlayWarningRecorded) {
                overlayWarningRecorded = true
                recordFailedAttempt(this, prefs, "تم إلغاء صلاحية شاشة القفل")
            }
''',
        '''            if (!overlayWarningRecorded) {
                overlayWarningRecorded = true
                appendGuardLog("OVERLAY_PERMISSION_MISSING")
                recordFailedAttempt(this, prefs, "تم إلغاء صلاحية شاشة القفل")
            }
''',
        "تشخيص إلغاء صلاحية الظهور",
    )
    native = replace_once(
        native,
        '''class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.guardPrefs()
        if (!prefs.getBoolean("enabled", false)) return

        val isWatchdog = intent?.action == MONITOR_WATCHDOG_ACTION
        val heartbeatAge = System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)
        val serviceNeedsRestart = !isWatchdog || heartbeatAge < 0L || heartbeatAge > STALE_HEARTBEAT_MS

        if (serviceNeedsRestart) context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)
        context.scheduleMonitorWatchdog()
    }
}
''',
        '''class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.guardPrefs()
        val enabled = prefs.getBoolean("enabled", false)
        context.appendGuardLog("BOOT_RECEIVER", "action=${intent?.action.orEmpty()} enabled=$enabled")
        if (!enabled) return

        val isWatchdog = intent?.action == MONITOR_WATCHDOG_ACTION
        val heartbeatAge = System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)
        val serviceNeedsRestart = !isWatchdog || heartbeatAge < 0L || heartbeatAge > STALE_HEARTBEAT_MS
        context.appendGuardLog(
            "WATCHDOG_DECISION",
            "isWatchdog=$isWatchdog heartbeatAge=$heartbeatAge restart=$serviceNeedsRestart",
        )

        try {
            if (serviceNeedsRestart) context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)
            context.scheduleMonitorWatchdog()
        } catch (error: Exception) {
            context.appendGuardLog("BOOT_RECEIVER_ERROR", error = error)
        }
    }
}
''',
        "تشخيص مستقبل الإقلاع والمراقب",
    )
    NATIVE_PATH.write_text(native, encoding="utf-8")
else:
    print("سجل التشخيص الأصلي مدمج مسبقاً")


dart = DART_PATH.read_text(encoding="utf-8")
if DART_MARKER not in dart:
    dart = replace_once(
        dart,
        '''  Future<void> _resolveDiagnosticAction(GuardDiagnosticAction action) async {
''',
        '''  // RUNTIME_DIAGNOSTICS_UI_MARKER
  Future<void> _showDiagnosticLog() async {
    try {
      final log =
          await _channel.invokeMethod<String>('getDiagnosticLog') ?? '';
      if (!mounted) return;

      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('سجل تشخيص التطبيق'),
          content: SizedBox(
            width: double.maxFinite,
            height: 480,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Scrollbar(
                  child: SingleChildScrollView(
                    child: SelectableText(
                      log.isEmpty ? 'لا توجد بيانات مسجلة بعد.' : log,
                      textDirection: TextDirection.ltr,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          actions: [
            TextButton.icon(
              onPressed: log.isEmpty
                  ? null
                  : () async {
                      await Clipboard.setData(ClipboardData(text: log));
                      _showMessage('تم نسخ سجل التشخيص.');
                    },
              icon: const Icon(Icons.copy_all_outlined),
              label: const Text('نسخ السجل'),
            ),
            TextButton.icon(
              onPressed: () async {
                await _channel.invokeMethod<void>('clearDiagnosticLog');
                if (dialogContext.mounted) Navigator.pop(dialogContext);
                _showMessage('تم مسح السجل وبدأ تسجيل جديد.');
              },
              icon: const Icon(Icons.delete_sweep_outlined),
              label: const Text('مسح'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر قراءة سجل التشخيص.');
    }
  }

  Future<void> _resolveDiagnosticAction(GuardDiagnosticAction action) async {
''',
        "واجهة عرض سجل التشخيص",
    )
    dart = replace_once(
        dart,
        '''            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: Badge(
''',
        '''            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(Icons.bug_report_outlined),
                title: const Text('سجل تشخيص التطبيق'),
                subtitle: const Text(
                  'يعرض تشغيل الخدمة، احتساب الوقت، المراقب ومحاولات القفل.',
                ),
                trailing: const Icon(Icons.chevron_left),
                onTap: _showDiagnosticLog,
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: Badge(
''',
        "بطاقة سجل التشخيص",
    )
    DART_PATH.write_text(dart, encoding="utf-8")
else:
    print("واجهة سجل التشخيص مدمجة مسبقاً")

print("تم دمج سجل التشخيص الدائم وحماية دورة العداد")
