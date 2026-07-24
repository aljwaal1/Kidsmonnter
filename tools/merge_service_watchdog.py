from pathlib import Path

SOURCE = Path('native/MainActivityV2.kt')
text = SOURCE.read_text(encoding='utf-8')

if 'MONITOR_WATCHDOG_ACTION' not in text:
    text = text.replace(
        'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\n',
        'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\n'
        'private const val MONITOR_WATCHDOG_ACTION = "com.explapp.kidstimeguard.RESTART_MONITOR"\n'
        'private const val WATCHDOG_REQUEST_CODE = 991\n'
        'private const val WATCHDOG_INTERVAL_MS = 60_000L\n'
        'private const val STALE_HEARTBEAT_MS = 30_000L\n',
    )

old_start_helper = '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}
'''
new_start_helper = '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}

private fun Context.scheduleMonitorWatchdog(delayMs: Long = WATCHDOG_INTERVAL_MS) {
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
'''
if 'private fun Context.scheduleMonitorWatchdog' not in text:
    if old_start_helper not in text:
        raise SystemExit('startMonitorServiceSafely block not found')
    text = text.replace(old_start_helper, new_start_helper)

old_create = '''        resetClockAnchor()
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        handler.post(ticker)
'''
new_create = '''        resetClockAnchor()
        startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))
        scheduleMonitorWatchdog()
        handler.post(ticker)
'''
if 'startForeground(NOTIFICATION_ID, buildGuardNotification("الحماية تعمل الآن"))\n        scheduleMonitorWatchdog()' not in text:
    if old_create not in text:
        raise SystemExit('MonitorService.onCreate anchor not found')
    text = text.replace(old_create, new_create)

old_restart = '''    private fun scheduleRestart() {
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
'''
new_restart = '''    private fun scheduleRestart() {
        if (!prefs.getBoolean("enabled", false)) return
        scheduleMonitorWatchdog(2_000L)
    }
'''
if 'scheduleMonitorWatchdog(2_000L)' not in text:
    if old_restart not in text:
        raise SystemExit('legacy scheduleRestart block not found')
    text = text.replace(old_restart, new_restart)

old_receiver = '''class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.guardPrefs()
        if (prefs.getBoolean("enabled", false)) context.startMonitorServiceSafely()
    }
}
'''
new_receiver = '''class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.guardPrefs()
        if (!prefs.getBoolean("enabled", false)) return

        val isWatchdog = intent?.action == MONITOR_WATCHDOG_ACTION
        val heartbeatAge = System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)
        val serviceNeedsRestart = !isWatchdog || heartbeatAge < 0L || heartbeatAge > STALE_HEARTBEAT_MS

        if (serviceNeedsRestart) context.startMonitorServiceSafely()
        context.scheduleMonitorWatchdog()
    }
}
'''
if 'val isWatchdog = intent?.action == MONITOR_WATCHDOG_ACTION' not in text:
    if old_receiver not in text:
        raise SystemExit('BootReceiver block not found')
    text = text.replace(old_receiver, new_receiver)

SOURCE.write_text(text, encoding='utf-8')
