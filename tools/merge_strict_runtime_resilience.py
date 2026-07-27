from pathlib import Path

NATIVE = Path("native/MainActivityV2.kt")
MANIFEST = Path("native/AndroidManifest.xml")
DART = Path("lib/main.dart")
MARKER = "STRICT_RUNTIME_RESILIENCE_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: لم يتم العثور على المقطع المتوقع")
    return text.replace(old, new, 1)


native = NATIVE.read_text(encoding="utf-8")
if MARKER not in native:
    native = replace_once(
        native,
        'private const val DIAGNOSTIC_HEARTBEAT_INTERVAL_MS = 15_000L\n',
        'private const val DIAGNOSTIC_HEARTBEAT_INTERVAL_MS = 15_000L\n'
        'private const val BOOT_PREFS_NAME = "kidsmonnter_boot"\n'
        'private const val BOOT_ENABLED_KEY = "protection_enabled"\n'
        'private const val BOOT_RETRY_ACTION = "com.explapp.kidstimeguard.BOOT_RETRY"\n'
        'private const val BOOT_RETRY_REQUEST_BASE = 1200\n'
        'private const val WAKE_LOCK_TIMEOUT_MS = 12_000L\n',
        "ثوابت الاستمرارية الصارمة",
    )
    native = replace_once(
        native,
        'private fun Context.guardPrefs(): SharedPreferences =\n    getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)\n',
        '''private fun Context.guardPrefs(): SharedPreferences =
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
''',
        "تخزين الإقلاع المحمي",
    )
    native = replace_once(
        native,
        '''private fun Context.scheduleMonitorWatchdog(delayMs: Long = WATCHDOG_INTERVAL_MS) {
    val pending = PendingIntent.getBroadcast(
        this,
        WATCHDOG_REQUEST_CODE,
        Intent(this, BootReceiver::class.java).setAction(MONITOR_WATCHDOG_ACTION),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )
    (getSystemService(Context.ALARM_SERVICE) as AlarmManager).setAndAllowWhileIdle(
        AlarmManager.ELAPSED_REALTIME_WAKEUP,
        SystemClock.elapsedRealtime() + delayMs,
        pending,
    )
}
''',
        '''private fun Context.scheduleMonitorWatchdog(delayMs: Long = WATCHDOG_INTERVAL_MS) {
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
''',
        "المراقب الدقيق وإعادات الإقلاع",
    )
    native = replace_once(
        native,
        '''                    appendGuardLog("PROTECTION_ENABLED", "minutes=$minutes used=${prefs.getInt("used_seconds", 0)}")
                    requestNotificationPermissionIfNeeded()
''',
        '''                    syncBootProtectionState(true)
                    appendGuardLog("PROTECTION_ENABLED", "minutes=$minutes used=${prefs.getInt("used_seconds", 0)}")
                    requestNotificationPermissionIfNeeded()
''',
        "مزامنة تفعيل الإقلاع",
    )
    native = replace_once(
        native,
        '''                        appendGuardLog("PROTECTION_DISABLED", "source=main_activity")
                        releaseDeviceOwnerPolicies()
''',
        '''                        syncBootProtectionState(false)
                        appendGuardLog("PROTECTION_DISABLED", "source=main_activity")
                        releaseDeviceOwnerPolicies()
''',
        "مزامنة إيقاف الحماية من التطبيق",
    )
    native = replace_once(
        native,
        '''        releaseDeviceOwnerPolicies()
        dismissLockOverlay()
        stopSelf()
''',
        '''        syncBootProtectionState(false)
        releaseDeviceOwnerPolicies()
        dismissLockOverlay()
        stopSelf()
''',
        "مزامنة إيقاف الحماية من النافذة",
    )
    native = replace_once(
        native,
        '''        releaseDeviceOwnerPolicies()
        stopService(Intent(this, MonitorService::class.java))
        exitLock()
''',
        '''        syncBootProtectionState(false)
        releaseDeviceOwnerPolicies()
        stopService(Intent(this, MonitorService::class.java))
        exitLock()
''',
        "مزامنة إيقاف الحماية من شاشة القفل",
    )
    native = replace_once(
        native,
        '''                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) {
''',
        '''                "openExactAlarmSettings" -> {
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
                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) {
''',
        "قنوات إعداد الاستمرارية",
    )
    native = replace_once(
        native,
        '''                        "overlayAllowed" to Settings.canDrawOverlays(this),
                        "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L)
''',
        '''                        "overlayAllowed" to Settings.canDrawOverlays(this),
                        "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L),
                        "exactAlarmAllowed" to canUseExactWatchdog(),
                        "batteryOptimizationIgnored" to isIgnoringBatteryOptimizations()
''',
        "حالة الاستمرارية في الواجهة",
    )
    native = replace_once(
        native,
        '''    override fun onCreate() {
        super.onCreate()
        appendGuardLog("SERVICE_CREATED", "enabled=${prefs.getBoolean("enabled", false)}")
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
''',
        '''    override fun onCreate() {
        super.onCreate()
        createChannel(this, GUARD_CHANNEL_ID, "حماية وقت الهاتف", NotificationManager.IMPORTANCE_LOW)
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        appendGuardLog("SERVICE_CREATED", "enabled=${prefs.getBoolean("enabled", false)}")
''',
        "ترقية الخدمة فورًا",
    )
    native = replace_once(
        native,
        '''        resetClockAnchor()
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        scheduleMonitorWatchdog()
''',
        '''        resetClockAnchor()
        scheduleMonitorWatchdog()
''',
        "إزالة الترقية المتأخرة",
    )
    native = replace_once(
        native,
        '''    override fun onDestroy() {
        appendGuardLog("SERVICE_DESTROYED", "enabled=${prefs.getBoolean("enabled", false)}")
        accountElapsedUsage()
        dismissLockOverlay()
        handler.removeCallbacks(ticker)
        try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
        if (prefs.getBoolean("enabled", false)) scheduleRestart()
        super.onDestroy()
    }
''',
        '''    override fun onDestroy() {
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
''',
        "حماية تدمير الخدمة",
    )
    start = native.index("class BootReceiver : BroadcastReceiver() {")
    native = native[:start] + '''class BootReceiver : BroadcastReceiver() {
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
                    context.requestMonitorServiceStartIfAllowed(
                        prefs,
                        force = action != MONITOR_WATCHDOG_ACTION,
                    )
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
'''
    NATIVE.write_text(native, encoding="utf-8")

manifest = MANIFEST.read_text(encoding="utf-8")
manifest = replace_once(
    manifest,
    '    <uses-permission android:name="android.permission.WAKE_LOCK" />\n',
    '    <uses-permission android:name="android.permission.WAKE_LOCK" />\n'
    '    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />\n'
    '    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />\n',
    "صلاحيات الاستمرارية",
)
manifest = replace_once(
    manifest,
    '            android:name=".BootReceiver"\n            android:enabled="true"',
    '            android:name=".BootReceiver"\n            android:directBootAware="true"\n            android:enabled="true"',
    "وعي مستقبل الإقلاع بالتشفير",
)
manifest = replace_once(
    manifest,
    '                <action android:name="com.explapp.kidstimeguard.RESTART_MONITOR" />\n',
    '                <action android:name="com.explapp.kidstimeguard.RESTART_MONITOR" />\n'
    '                <action android:name="com.explapp.kidstimeguard.BOOT_RETRY" />\n',
    "إجراء إعادة محاولة الإقلاع",
)
MANIFEST.write_text(manifest, encoding="utf-8")

dart = DART.read_text(encoding="utf-8")
if "STRICT_RUNTIME_UI_MARKER" not in dart:
    dart = replace_once(
        dart,
        '  String? _error;\n',
        '  String? _error;\n'
        '  bool _exactAlarmAllowed = false;\n'
        '  bool _batteryOptimizationIgnored = false;\n',
        "حالة واجهة الاستمرارية",
    )
    dart = replace_once(
        dart,
        '''      setState(() {
        _status = GuardStatus.fromMap(map, overlay);
        _devicePolicy = DevicePolicyStatus.fromMap(policyMap);
        _error = null;
      });
''',
        '''      setState(() {
        _status = GuardStatus.fromMap(map, overlay);
        _devicePolicy = DevicePolicyStatus.fromMap(policyMap);
        _exactAlarmAllowed = map['exactAlarmAllowed'] == true;
        _batteryOptimizationIgnored = map['batteryOptimizationIgnored'] == true;
        _error = null;
      });
''',
        "قراءة حالة الاستمرارية",
    )
    dart = replace_once(
        dart,
        '  int get _limitSeconds => (_status?.dailyMinutes ?? 60) * 60;\n',
        '''  // STRICT_RUNTIME_UI_MARKER
  Future<void> _openStrictSetting(String method) async {
    try {
      await _channel.invokeMethod<void>(method);
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر فتح إعداد النظام.');
    }
  }

  Widget _buildStrictRuntimeCard() {
    final ready = _exactAlarmAllowed && _batteryOptimizationIgnored;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(ready ? Icons.verified_user : Icons.warning_amber_rounded),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    ready ? 'استمرارية الخلفية مضبوطة' : 'يلزم تشديد تشغيل الخلفية',
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(_exactAlarmAllowed
                ? 'مراقب الاستعادة الدقيق مفعّل.'
                : 'فعّل المنبهات والتذكيرات حتى يستطيع المراقب إعادة الخدمة.'),
            const SizedBox(height: 6),
            Text(_batteryOptimizationIgnored
                ? 'التطبيق مستثنى من تحسين البطارية.'
                : 'استثنِ التطبيق من تحسين البطارية لمنع النظام من تجميده.'),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!_exactAlarmAllowed)
                  FilledButton.tonal(
                    onPressed: () => _openStrictSetting('openExactAlarmSettings'),
                    child: const Text('تفعيل المنبه الدقيق'),
                  ),
                if (!_batteryOptimizationIgnored)
                  FilledButton.tonal(
                    onPressed: () =>
                        _openStrictSetting('openBatteryOptimizationSettings'),
                    child: const Text('استثناء البطارية'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  int get _limitSeconds => (_status?.dailyMinutes ?? 60) * 60;
''',
        "بطاقة الاستمرارية الصارمة",
    )
    dart = replace_once(
        dart,
        '''            GuardDiagnosticsCard(
              diagnostics: status.diagnostics,
''',
        '''            _buildStrictRuntimeCard(),
            const SizedBox(height: 14),
            GuardDiagnosticsCard(
              diagnostics: status.diagnostics,
''',
        "إظهار بطاقة الاستمرارية",
    )
    DART.write_text(dart, encoding="utf-8")

print("Strict runtime resilience merged")
