#!/usr/bin/env python3
from pathlib import Path

path = Path('native/MainActivityV2.kt')
source = path.read_text(encoding='utf-8')

helper_marker = '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}
'''
helper = helper_marker + '''
private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = System.currentTimeMillis()
    val age = now - heartbeat
    return age > 30_000L || age < -5_000L
}
'''

if 'private fun shouldRecoverProtectionService' not in source:
    if helper_marker not in source:
        raise SystemExit('startMonitorServiceSafely marker not found')
    source = source.replace(helper_marker, helper, 1)

old = '''                "getStatus" -> result.success(mapOf(
                    "enabled" to prefs.getBoolean("enabled", false),
                    "usedSeconds" to prefs.getInt("used_seconds", 0),
                    "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                    "hasPin" to hasStoredPin(prefs),
                    "failedAttempts" to readFailedAttempts(prefs).size,
                    "parentEmail" to prefs.getString(PARENT_EMAIL_KEY, "").orEmpty(),
                    "overlayAllowed" to Settings.canDrawOverlays(this),
                    "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L)
                ))
'''
new = '''                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) startMonitorServiceSafely()
                    result.success(mapOf(
                        "enabled" to prefs.getBoolean("enabled", false),
                        "usedSeconds" to prefs.getInt("used_seconds", 0),
                        "dailyMinutes" to prefs.getInt("daily_minutes", 60),
                        "hasPin" to hasStoredPin(prefs),
                        "failedAttempts" to readFailedAttempts(prefs).size,
                        "parentEmail" to prefs.getString(PARENT_EMAIL_KEY, "").orEmpty(),
                        "overlayAllowed" to Settings.canDrawOverlays(this),
                        "serviceHeartbeatMs" to prefs.getLong(HEARTBEAT_KEY, 0L)
                    ))
                }
'''

if 'if (shouldRecoverProtectionService(prefs)) startMonitorServiceSafely()' not in source:
    if old not in source:
        raise SystemExit('getStatus block not found')
    source = source.replace(old, new, 1)

path.write_text(source, encoding='utf-8')
