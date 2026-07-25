from pathlib import Path

native_path = Path("native/MainActivityV2.kt")
source = native_path.read_text(encoding="utf-8")

if "LAST_SERVICE_START_REQUEST_ELAPSED_KEY" not in source:
    marker = 'private const val STALE_HEARTBEAT_MS = 30_000L\n'
    addition = (
        'private const val LAST_SERVICE_START_REQUEST_ELAPSED_KEY = '
        '"last_service_start_request_elapsed_ms"\n'
        'private const val SERVICE_START_REQUEST_COOLDOWN_MS = 15_000L\n'
    )
    if marker not in source:
        raise SystemExit("Could not find service timing constants")
    source = source.replace(marker, marker + addition, 1)

helper = '''private fun Context.requestMonitorServiceStartIfAllowed(
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

'''

if "requestMonitorServiceStartIfAllowed" not in source:
    marker = "private fun Context.scheduleMonitorWatchdog"
    if marker not in source:
        raise SystemExit("Could not find restart cooldown insertion point")
    source = source.replace(marker, helper + marker, 1)

old_status = "if (shouldRecoverProtectionService(prefs)) startMonitorServiceSafely()"
new_status = (
    "if (shouldRecoverProtectionService(prefs)) "
    "requestMonitorServiceStartIfAllowed(prefs)"
)
if old_status in source:
    source = source.replace(old_status, new_status, 1)
elif new_status not in source:
    raise SystemExit("Could not update getStatus recovery path")

old_boot = "if (serviceNeedsRestart) context.startMonitorServiceSafely()"
new_boot = (
    "if (serviceNeedsRestart) "
    "context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)"
)
if old_boot in source:
    source = source.replace(old_boot, new_boot, 1)
elif new_boot not in source:
    raise SystemExit("Could not update watchdog recovery path")

old_heartbeat = (
    "prefs.edit().putLong(HEARTBEAT_KEY, System.currentTimeMillis()).apply()"
)
new_heartbeat = '''prefs.edit()
                .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
                .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)
                .apply()'''
if old_heartbeat in source:
    source = source.replace(old_heartbeat, new_heartbeat, 1)
elif "remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)" not in source:
    raise SystemExit("Could not clear restart cooldown after heartbeat")

native_path.write_text(source, encoding="utf-8")
