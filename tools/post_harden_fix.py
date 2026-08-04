from pathlib import Path

path = Path("android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt")
text = path.read_text(encoding="utf-8")

replacements = {
    'return "$PIN_HASH_PREFIX$$PIN_HASH_ITERATIONS$$saltText$$hashText"':
        'return "${PIN_HASH_PREFIX}:${PIN_HASH_ITERATIONS}:$saltText:$hashText"',
    "val parts = encoded.split('$')": "val parts = encoded.split(':')",
    'storedHash.startsWith("$PIN_HASH_PREFIX$")':
        'storedHash.startsWith("$PIN_HASH_PREFIX:")',
    '''private fun isUnlockedForTrustedDay(prefs: SharedPreferences): Boolean =
    !prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false) &&
        isUnlockedForTrustedDay(prefs)''':
        '''private fun isUnlockedForTrustedDay(prefs: SharedPreferences): Boolean =
    !prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false) &&
        prefs.getString("unlocked_date", "") == today()''',
    'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\n':
        'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\nprivate const val HEARTBEAT_ELAPSED_KEY = "service_heartbeat_elapsed_ms"\n',
    '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = SystemClock.elapsedRealtime()
    val age = now - heartbeat
    return age > STALE_HEARTBEAT_MS || age < 0L
}''':
        '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_ELAPSED_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = SystemClock.elapsedRealtime()
    val age = now - heartbeat
    return age > STALE_HEARTBEAT_MS || age < 0L
}''',
    '''prefs.edit()
                    .putLong(HEARTBEAT_KEY, SystemClock.elapsedRealtime())
                    .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)''':
        '''prefs.edit()
                    .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
                    .putLong(HEARTBEAT_ELAPSED_KEY, SystemClock.elapsedRealtime())
                    .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)''',
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Post-hardening fix expected one match, found {count}: {old[:80]}")
    text = text.replace(old, new, 1)

if 'PBKDF2WithHmacSHA256' not in text:
    raise SystemExit('PBKDF2 hardening marker missing')
if 'TIME_TAMPER_DETECTED' not in text:
    raise SystemExit('trusted-clock hardening marker missing')
if 'HEARTBEAT_ELAPSED_KEY' not in text:
    raise SystemExit('separate elapsed heartbeat marker missing')
if 'isUnlockedForTrustedDay(prefs)\n' in text.split('private fun isUnlockedForTrustedDay', 1)[1].split('\n\n', 1)[0]:
    raise SystemExit('trusted-day helper is recursive')

text += "\n// UNIFIED_SECURITY_HARDENING_V2_POSTFIX\n// DUAL_HEARTBEAT_CLOCK_FIX\n"
path.write_text(text, encoding="utf-8")
print('Post-hardening corrections applied successfully')
