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
    '''                    } else {
                        prefs.edit().putInt("daily_minutes", minutes).commit()
                        appendGuardLog(
                            "DAILY_MINUTES_UPDATED",
                            "minutes=$minutes protectionEnabled=${prefs.getBoolean("enabled", false)}",
                        )
                        result.success(true)
                    }''':
        '''                    } else {
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
                    }''',
}

for old, new in replacements.items():
    count = text.count(old)
    if count == 1:
        text = text.replace(old, new, 1)
    elif count == 0 and new in text:
        continue
    elif count == 0:
        # The preceding hardening stage may already implement an equivalent safe form.
        continue
    else:
        raise SystemExit(f"Post-hardening fix expected at most one old match, found {count}: {old[:80]}")

required = [
    'PBKDF2WithHmacSHA256',
    'TIME_TAMPER_DETECTED',
    'DURATION_CHANGE_REQUESTED',
    'DURATION_CHANGE_VERIFIED',
    'DURATION_SAVE_MISMATCH',
    '.putLong(HEARTBEAT_KEY, SystemClock.elapsedRealtime())',
    'val heartbeatAge = SystemClock.elapsedRealtime() - prefs.getLong(HEARTBEAT_KEY, 0L)',
]
for marker in required:
    if marker not in text:
        raise SystemExit(f'required post-hardening marker missing: {marker}')

# Heartbeat must use exactly one monotonic clock end-to-end.
for forbidden in [
    '.putLong(HEARTBEAT_KEY, System.currentTimeMillis())',
    'System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)',
    'HEARTBEAT_ELAPSED_KEY',
]:
    if forbidden in text:
        raise SystemExit(f'forbidden mixed heartbeat implementation present: {forbidden}')

if 'isUnlockedForTrustedDay(prefs)\n' in text.split('private fun isUnlockedForTrustedDay', 1)[1].split('\n\n', 1)[0]:
    raise SystemExit('trusted-day helper is recursive')

text += "\n// UNIFIED_SECURITY_HARDENING_V6_POSTFIX\n// SINGLE_MONOTONIC_HEARTBEAT_CLOCK\n// WATCHDOG_ELAPSED_CLOCK_ONLY\n// VERIFIED_DURATION_PERSISTENCE\n"
path.write_text(text, encoding="utf-8")
print('Post-hardening corrections applied successfully')
