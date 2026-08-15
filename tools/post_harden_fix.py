from pathlib import Path

path = Path("android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Post-hardening fix {label!r} expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


# PIN-format/trusted-day corrections produced by the main hardener.
optional_replacements = {
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
}
for old, new in optional_replacements.items():
    count = text.count(old)
    if count == 1:
        text = text.replace(old, new, 1)
    elif count == 0 and new in text:
        pass
    elif count != 0:
        raise SystemExit(f"Unexpected duplicate post-hardening match: {old[:80]}")

# Keep a wall-clock heartbeat for Flutter diagnostics and a separate monotonic
# heartbeat for watchdog/recovery decisions. Never compare the two clocks.
if 'private const val HEARTBEAT_ELAPSED_KEY = "service_heartbeat_elapsed_ms"' not in text:
    replace_once(
        'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\n',
        'private const val HEARTBEAT_KEY = "service_heartbeat_ms"\n'
        'private const val HEARTBEAT_ELAPSED_KEY = "service_heartbeat_elapsed_ms"\n',
        'dual heartbeat constant',
    )

# The main hardener converts shouldRecoverProtectionService to elapsedRealtime
# while still reading HEARTBEAT_KEY. Point that recovery-only read to the
# monotonic heartbeat key.
old_recovery = '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = SystemClock.elapsedRealtime()
    val age = now - heartbeat
    return age > STALE_HEARTBEAT_MS || age < 0L
}'''
new_recovery = '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_ELAPSED_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = SystemClock.elapsedRealtime()
    val age = now - heartbeat
    return age > STALE_HEARTBEAT_MS || age < 0L
}'''
if old_recovery in text:
    replace_once(old_recovery, new_recovery, 'recovery elapsed heartbeat')
elif new_recovery not in text:
    raise SystemExit('Recovery helper is not in a recognized heartbeat form')

# Ticker stores both clocks atomically: wall time for presentation, monotonic
# time for service liveness decisions.
old_ticker = '''prefs.edit()
                    .putLong(HEARTBEAT_KEY, SystemClock.elapsedRealtime())
                    .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)'''
new_ticker = '''prefs.edit()
                    .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
                    .putLong(HEARTBEAT_ELAPSED_KEY, SystemClock.elapsedRealtime())
                    .remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)'''
if old_ticker in text:
    replace_once(old_ticker, new_ticker, 'ticker dual heartbeat')
elif new_ticker not in text:
    raise SystemExit('Ticker is not in a recognized heartbeat form')

# BootReceiver uses only the monotonic heartbeat. A value from a previous boot
# is treated as stale because elapsedRealtime resets at reboot.
old_boot = '''val heartbeatAge = SystemClock.elapsedRealtime() - prefs.getLong(HEARTBEAT_KEY, 0L)
            val serviceNeedsRestart =
                !isWatchdog || heartbeatAge < 0L || heartbeatAge > STALE_HEARTBEAT_MS'''
new_boot = '''val heartbeatElapsed = prefs.getLong(HEARTBEAT_ELAPSED_KEY, 0L)
            val nowElapsed = SystemClock.elapsedRealtime()
            val heartbeatAge = if (heartbeatElapsed <= 0L || heartbeatElapsed > nowElapsed) {
                Long.MAX_VALUE
            } else {
                nowElapsed - heartbeatElapsed
            }
            val serviceNeedsRestart =
                !isWatchdog || heartbeatAge > STALE_HEARTBEAT_MS'''
if old_boot in text:
    replace_once(old_boot, new_boot, 'boot elapsed heartbeat')
elif new_boot not in text:
    raise SystemExit('BootReceiver is not in a recognized heartbeat form')

# Verify duration persistence instead of trusting SharedPreferences.commit().
old_duration = '''                    } else {
                        prefs.edit().putInt("daily_minutes", minutes).commit()
                        appendGuardLog(
                            "DAILY_MINUTES_UPDATED",
                            "minutes=$minutes protectionEnabled=${prefs.getBoolean("enabled", false)}",
                        )
                        result.success(true)
                    }'''
new_duration = '''                    } else {
                        val oldMinutes = prefs.getInt("daily_minutes", 10)
                        appendGuardLog(
                            "DURATION_CHANGE_REQUESTED",
                            "old=$oldMinutes requested=$minutes protectionEnabled=${prefs.getBoolean("enabled", false)}",
                        )
                        val saved = prefs.edit().putInt("daily_minutes", minutes).commit()
                        val actualMinutes = prefs.getInt("daily_minutes", -1)
                        if (!saved || actualMinutes != minutes) {
                            appendGuardLog(
                                "DURATION_CHANGE_FAILED",
                                "old=$oldMinutes requested=$minutes actual=$actualMinutes commit=$saved",
                            )
                            result.error(
                                "DURATION_SAVE_MISMATCH",
                                "تعذر التحقق من حفظ المدة المطلوبة",
                                mapOf("requested" to minutes, "actual" to actualMinutes),
                            )
                        } else {
                            appendGuardLog(
                                "DURATION_CHANGE_VERIFIED",
                                "old=$oldMinutes requested=$minutes actual=$actualMinutes",
                            )
                            result.success(true)
                        }
                    }'''
if old_duration in text:
    replace_once(old_duration, new_duration, 'verified duration persistence')
elif new_duration not in text:
    raise SystemExit('Duration setter is not in a recognized form')

required = [
    'PBKDF2WithHmacSHA256',
    'TIME_TAMPER_DETECTED',
    'HEARTBEAT_ELAPSED_KEY',
    '.putLong(HEARTBEAT_KEY, System.currentTimeMillis())',
    '.putLong(HEARTBEAT_ELAPSED_KEY, SystemClock.elapsedRealtime())',
    'val heartbeatElapsed = prefs.getLong(HEARTBEAT_ELAPSED_KEY, 0L)',
    'DURATION_CHANGE_REQUESTED',
    'DURATION_CHANGE_VERIFIED',
    'DURATION_SAVE_MISMATCH',
]
for marker in required:
    if marker not in text:
        raise SystemExit(f'required post-hardening marker missing: {marker}')

for forbidden in [
    'System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)',
    'SystemClock.elapsedRealtime() - prefs.getLong(HEARTBEAT_KEY, 0L)',
]:
    if forbidden in text:
        raise SystemExit(f'mixed heartbeat clock comparison still present: {forbidden}')

if 'isUnlockedForTrustedDay(prefs)\n' in text.split('private fun isUnlockedForTrustedDay', 1)[1].split('\n\n', 1)[0]:
    raise SystemExit('trusted-day helper is recursive')

text += "\n// UNIFIED_SECURITY_HARDENING_V7_POSTFIX\n// DUAL_HEARTBEAT_CLOCK_FIX\n// WATCHDOG_ELAPSED_CLOCK_ONLY\n// DIAGNOSTIC_WALL_CLOCK_ONLY\n// VERIFIED_DURATION_PERSISTENCE\n"
path.write_text(text, encoding="utf-8")
print('Post-hardening corrections applied successfully')
