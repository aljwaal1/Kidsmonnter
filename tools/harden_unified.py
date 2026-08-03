from pathlib import Path

path = Path("android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Hardening patch {label!r} expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


def replace_all(old: str, new: str, label: str, minimum: int = 1) -> None:
    global text
    count = text.count(old)
    if count < minimum:
        raise SystemExit(f"Hardening patch {label!r} expected at least {minimum} matches, found {count}")
    text = text.replace(old, new)


replace_once(
    "import java.security.MessageDigest\n",
    "import java.security.MessageDigest\nimport java.security.SecureRandom\nimport javax.crypto.SecretKeyFactory\nimport javax.crypto.spec.PBEKeySpec\nimport kotlin.math.abs\n",
    "security imports",
)

replace_once(
    'private const val SETTINGS_AUTH_WINDOW_MS = 90_000L\n',
    '''private const val SETTINGS_AUTH_WINDOW_MS = 90_000L
private const val PIN_HASH_PREFIX = "pbkdf2_sha256"
private const val PIN_HASH_ITERATIONS = 210_000
private const val PIN_SALT_BYTES = 16
private const val PIN_DERIVED_KEY_BITS = 256
private const val TIME_TAMPER_DETECTED_KEY = "time_tamper_detected"
private const val TRUSTED_WALL_CLOCK_KEY = "trusted_wall_clock_ms"
private const val TRUSTED_ELAPSED_CLOCK_KEY = "trusted_elapsed_clock_ms"
private const val TIME_TAMPER_TOLERANCE_MS = 10 * 60_000L
private const val RECOVERY_REQUIRED_KEY = "parent_recovery_required"
''',
    "hardening constants",
)

replace_once(
    '''private fun SharedPreferences.isParentUninstallAuthorized(): Boolean =
    System.currentTimeMillis() <= getLong(UNINSTALL_AUTHORIZED_UNTIL_KEY, 0L)
''',
    '''private fun SharedPreferences.isParentUninstallAuthorized(): Boolean {
    val now = SystemClock.elapsedRealtime()
    val until = getLong(UNINSTALL_AUTHORIZED_UNTIL_KEY, 0L)
    return until >= now && until - now <= UNINSTALL_AUTH_WINDOW_MS
}
''',
    "elapsed uninstall authorization",
)

replace_once(
    '''private fun hashPin(pin: String): String {
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
''',
    '''private fun legacyHashPin(pin: String): String {
    val bytes = MessageDigest.getInstance("SHA-256")
        .digest("KidsMonnter:$pin".toByteArray(Charsets.UTF_8))
    return bytes.joinToString("") { "%02x".format(it) }
}

private fun derivePinKey(pin: String, salt: ByteArray, iterations: Int): ByteArray {
    val spec = PBEKeySpec(pin.toCharArray(), salt, iterations, PIN_DERIVED_KEY_BITS)
    return try {
        SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
    } finally {
        spec.clearPassword()
    }
}

private fun encodePin(pin: String): String {
    val salt = ByteArray(PIN_SALT_BYTES).also { SecureRandom().nextBytes(it) }
    val derived = derivePinKey(pin, salt, PIN_HASH_ITERATIONS)
    val saltText = android.util.Base64.encodeToString(salt, android.util.Base64.NO_WRAP)
    val hashText = android.util.Base64.encodeToString(derived, android.util.Base64.NO_WRAP)
    return "$PIN_HASH_PREFIX$$PIN_HASH_ITERATIONS$$saltText$$hashText"
}

private fun verifyModernPin(encoded: String, candidate: String): Boolean {
    val parts = encoded.split('$')
    if (parts.size != 4 || parts[0] != PIN_HASH_PREFIX) return false
    val iterations = parts[1].toIntOrNull()?.takeIf { it in 100_000..1_000_000 } ?: return false
    return try {
        val salt = android.util.Base64.decode(parts[2], android.util.Base64.NO_WRAP)
        val expected = android.util.Base64.decode(parts[3], android.util.Base64.NO_WRAP)
        MessageDigest.isEqual(expected, derivePinKey(candidate, salt, iterations))
    } catch (_: IllegalArgumentException) {
        false
    }
}

private fun hasStoredPin(prefs: SharedPreferences): Boolean =
    prefs.getString(PIN_HASH_KEY, "").orEmpty().isNotBlank() ||
        prefs.getString(LEGACY_PIN_KEY, "").orEmpty().length == 6

private fun verifyPin(prefs: SharedPreferences, candidate: String): Boolean {
    if (candidate.length != 6 || candidate.any { !it.isDigit() }) return false
    if (lockPinBlockRemainingMs(prefs) > 0L) return false

    val storedHash = prefs.getString(PIN_HASH_KEY, "").orEmpty()
    if (storedHash.startsWith("$PIN_HASH_PREFIX$")) {
        return verifyModernPin(storedHash, candidate)
    }
    if (storedHash.isNotBlank() && MessageDigest.isEqual(
            storedHash.toByteArray(Charsets.UTF_8),
            legacyHashPin(candidate).toByteArray(Charsets.UTF_8),
        )
    ) {
        prefs.edit().putString(PIN_HASH_KEY, encodePin(candidate)).commit()
        return true
    }

    val legacy = prefs.getString(LEGACY_PIN_KEY, "").orEmpty()
    if (legacy == candidate) {
        prefs.edit().putString(PIN_HASH_KEY, encodePin(candidate)).remove(LEGACY_PIN_KEY).commit()
        return true
    }
    return false
}
''',
    "PBKDF2 PIN storage",
)

replace_once(
    '''    val remaining = until - System.currentTimeMillis()
''',
    '''    val remaining = until - SystemClock.elapsedRealtime()
''',
    "elapsed PIN block read",
)
replace_once(
    '''        .putLong(PIN_BLOCK_UNTIL_MS_KEY, System.currentTimeMillis() + delayMs)
''',
    '''        .putLong(PIN_BLOCK_UNTIL_MS_KEY, SystemClock.elapsedRealtime() + delayMs)
''',
    "elapsed PIN block write",
)

replace_once(
    '''private fun Context.disableProtectionFailOpen(reason: String) {
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
''',
    '''private fun Context.disableProtectionFailOpen(reason: String) {
    val prefs = guardPrefs()
    prefs.edit()
        .putBoolean("enabled", true)
        .putBoolean(RECOVERY_REQUIRED_KEY, true)
        .remove("unlocked_date")
        .commit()
    syncBootProtectionState(true)
    appendGuardLog("LOCK_FAIL_SAFE", "reason=$reason protectionRetained=true")
}
''',
    "fail-safe recovery",
)

replace_once(
    '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = System.currentTimeMillis()
    val age = now - heartbeat
    return age > 30_000L || age < -5_000L
}
''',
    '''private fun shouldRecoverProtectionService(prefs: SharedPreferences): Boolean {
    if (!prefs.getBoolean("enabled", false)) return false
    val heartbeat = prefs.getLong(HEARTBEAT_KEY, 0L)
    if (heartbeat <= 0L) return true
    val now = SystemClock.elapsedRealtime()
    val age = now - heartbeat
    return age > STALE_HEARTBEAT_MS || age < 0L
}

private fun updateTrustedClockBaseline(prefs: SharedPreferences) {
    prefs.edit()
        .putLong(TRUSTED_WALL_CLOCK_KEY, System.currentTimeMillis())
        .putLong(TRUSTED_ELAPSED_CLOCK_KEY, SystemClock.elapsedRealtime())
        .apply()
}

private fun Context.detectTimeTamper(prefs: SharedPreferences): Boolean {
    if (prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false)) return true
    val wallNow = System.currentTimeMillis()
    val elapsedNow = SystemClock.elapsedRealtime()
    val wallBefore = prefs.getLong(TRUSTED_WALL_CLOCK_KEY, 0L)
    val elapsedBefore = prefs.getLong(TRUSTED_ELAPSED_CLOCK_KEY, 0L)
    var tampered = false
    if (wallBefore > 0L && elapsedBefore > 0L && elapsedNow >= elapsedBefore) {
        val wallDelta = wallNow - wallBefore
        val elapsedDelta = elapsedNow - elapsedBefore
        tampered = wallDelta < -120_000L || abs(wallDelta - elapsedDelta) > TIME_TAMPER_TOLERANCE_MS
    }
    prefs.edit()
        .putLong(TRUSTED_WALL_CLOCK_KEY, wallNow)
        .putLong(TRUSTED_ELAPSED_CLOCK_KEY, elapsedNow)
        .putBoolean(TIME_TAMPER_DETECTED_KEY, tampered)
        .apply()
    if (tampered) appendGuardLog("TIME_TAMPER_DETECTED", "wallBefore=$wallBefore wallNow=$wallNow elapsedBefore=$elapsedBefore elapsedNow=$elapsedNow")
    return tampered
}

private fun isUnlockedForTrustedDay(prefs: SharedPreferences): Boolean =
    !prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false) &&
        prefs.getString("unlocked_date", "") == today()
''',
    "trusted clock helpers",
)

replace_once(
    '''                "setPin" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (pin.length != 6 || pin.any { !it.isDigit() }) {
                        result.error("INVALID_PIN", "PIN must be 6 digits", null)
                    } else {
                        prefs.edit().putString(PIN_HASH_KEY, hashPin(pin)).remove(LEGACY_PIN_KEY).commit()
                        result.success(true)
                    }
                }
''',
    '''                "setPin" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (pin.length != 6 || pin.any { !it.isDigit() }) {
                        result.error("INVALID_PIN", "PIN must be 6 digits", null)
                    } else if (hasStoredPin(prefs)) {
                        result.error("PIN_ALREADY_SET", "استخدم مسار تغيير الرمز بعد التحقق من الرمز الحالي", null)
                    } else {
                        prefs.edit()
                            .putString(PIN_HASH_KEY, encodePin(pin))
                            .remove(LEGACY_PIN_KEY)
                            .remove(RECOVERY_REQUIRED_KEY)
                            .commit()
                        clearLockPinFailureState(prefs)
                        result.success(true)
                    }
                }
                "changePin" -> {
                    val oldPin = call.argument<String>("oldPin").orEmpty()
                    val newPin = call.argument<String>("newPin").orEmpty()
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        result.error("PIN_TEMPORARILY_BLOCKED", lockDelayText(remaining), remaining)
                    } else if (!verifyPin(prefs, oldPin)) {
                        val delay = registerLockPinFailure(this, prefs, "محاولة تغيير رمز ولي الأمر")
                        result.error("WRONG_PIN", "رمز ولي الأمر الحالي غير صحيح. ${lockDelayText(delay)}", delay)
                    } else if (newPin.length != 6 || newPin.any { !it.isDigit() }) {
                        result.error("INVALID_PIN", "PIN must be 6 digits", null)
                    } else {
                        prefs.edit().putString(PIN_HASH_KEY, encodePin(newPin)).remove(LEGACY_PIN_KEY).commit()
                        clearLockPinFailureState(prefs)
                        result.success(true)
                    }
                }
''',
    "secure PIN set/change",
)

replace_once(
    '''                    val minutes = (call.argument<Int>("minutes") ?: 10).coerceIn(1, 1440)
                    prefs.edit()
                        .putInt("daily_minutes", minutes)
                        .putBoolean("enabled", true)
                        .putString("date", today())
                        .remove("unlocked_date")
                        .remove(LAST_TICK_KEY)
                        .commit()
''',
    '''                    val minutes = (call.argument<Int>("minutes") ?: 10).coerceIn(1, 1440)
                    val currentDate = today()
                    val previousDate = prefs.getString("date", "").orEmpty()
                    val editor = prefs.edit()
                        .putInt("daily_minutes", minutes)
                        .putBoolean("enabled", true)
                        .putString("date", currentDate)
                        .putBoolean(TIME_TAMPER_DETECTED_KEY, false)
                        .remove(RECOVERY_REQUIRED_KEY)
                        .remove("unlocked_date")
                        .remove(LAST_TICK_KEY)
                    if (previousDate != currentDate) editor.putInt("used_seconds", 0)
                    if (!editor.commit()) {
                        result.error("STATE_SAVE_FAILED", "تعذر حفظ حالة الحماية", null)
                        return@setMethodCallHandler
                    }
                    updateTrustedClockBaseline(prefs)
''',
    "safe daily reset on start",
)

replace_all(
    'prefs.getString("unlocked_date", "") == today()',
    'isUnlockedForTrustedDay(prefs)',
    "trusted unlocked-day checks",
    minimum=4,
)

replace_once(
    '''                resetIfNewDay()
                prefs.edit()
                    .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
''',
    '''                detectTimeTamper(prefs)
                resetIfNewDay()
                prefs.edit()
                    .putLong(HEARTBEAT_KEY, SystemClock.elapsedRealtime())
''',
    "ticker trusted time and elapsed heartbeat",
)

replace_once(
    '''    private fun resetIfNewDay() {
        val currentDate = today()
        if (prefs.getString("date", "") == currentDate) return
        prefs.edit().putString("date", currentDate).putInt("used_seconds", 0)
            .remove("unlocked_date").remove(LAST_TICK_KEY).commit()
        overlayWarningRecorded = false
        resetClockAnchor("new_day")
    }
''',
    '''    private fun resetIfNewDay() {
        if (prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false)) {
            appendGuardLog("NEW_DAY_RESET_BLOCKED", "reason=time_tamper")
            return
        }
        val currentDate = today()
        if (prefs.getString("date", "") == currentDate) return
        prefs.edit().putString("date", currentDate).putInt("used_seconds", 0)
            .remove("unlocked_date").remove(LAST_TICK_KEY).commit()
        updateTrustedClockBaseline(prefs)
        overlayWarningRecorded = false
        resetClockAnchor("new_day")
    }
''',
    "tamper-safe day reset",
)

replace_once(
    '''        if (!hasStoredPin(prefs)) {
            appendGuardLog("LOCK_ABORTED_INVALID_PIN_STATE")
            disableProtectionFailOpen("missing_or_corrupt_parent_pin")
            dismissLockOverlay()
            stopSelf()
            return
        }
''',
    '''        if (!hasStoredPin(prefs)) {
            appendGuardLog("LOCK_RECOVERY_REQUIRED_INVALID_PIN_STATE")
            disableProtectionFailOpen("missing_or_corrupt_parent_pin")
            val limit = prefs.getInt("daily_minutes", 10).coerceAtLeast(1) * 60
            prefs.edit().putInt("used_seconds", limit).commit()
            showLock()
            if (screenOn) launchLockActivityReliably()
            return
        }
''',
    "fail-safe missing PIN enforcement",
)

replace_once(
    '''                UNINSTALL_AUTHORIZED_UNTIL_KEY,
                System.currentTimeMillis() + UNINSTALL_AUTH_WINDOW_MS,
''',
    '''                UNINSTALL_AUTHORIZED_UNTIL_KEY,
                SystemClock.elapsedRealtime() + UNINSTALL_AUTH_WINDOW_MS,
''',
    "elapsed uninstall authorization write",
)

replace_once(
    '''            val heartbeatAge = System.currentTimeMillis() - prefs.getLong(HEARTBEAT_KEY, 0L)
''',
    '''            val heartbeatAge = SystemClock.elapsedRealtime() - prefs.getLong(HEARTBEAT_KEY, 0L)
''',
    "elapsed boot heartbeat",
)

# Apply the same escalating delay to native management calls that previously only logged failures.
for source in (
    "تأكيد إعدادات ولي الأمر",
    "إيقاف الحماية",
    "تغيير المدة اليومية",
    "إضافة وقت",
    "محاولة السماح بحذف التطبيق",
):
    text = text.replace(
        f'recordFailedAttempt(this, prefs, "{source}")',
        f'registerLockPinFailure(this, prefs, "{source}")',
    )

# LockActivity must use the same rate limiter as the overlay lock.
text = text.replace(
    '''        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, "إيقاف الحماية من شاشة القفل")
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
''',
    '''        val remaining = lockPinBlockRemainingMs(prefs)
        if (remaining > 0L) {
            statusView.text = lockDelayText(remaining)
            return
        }
        if (!verifyPin(prefs, pin)) {
            val delay = registerLockPinFailure(this, prefs, "إيقاف الحماية من شاشة القفل")
            statusView.text = "رمز ولي الأمر غير صحيح. ${lockDelayText(delay)}"
''',
)
text = text.replace(
    '''        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, source)
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
''',
    '''        val remaining = lockPinBlockRemainingMs(prefs)
        if (remaining > 0L) {
            statusView.text = lockDelayText(remaining)
            return
        }
        if (!verifyPin(prefs, pin)) {
            val delay = registerLockPinFailure(this, prefs, source)
            statusView.text = "رمز ولي الأمر غير صحيح. ${lockDelayText(delay)}"
''',
)

# Uninstall gate also receives escalating throttling.
replace_once(
    '''                setOnClickListener {
                    val candidate = pin.text.toString().trim()
                    if (!verifyPin(prefs, candidate)) {
                        recordFailedAttempt(
                            this@UninstallPinActivity,
                            prefs,
                            "محاولة حذف التطبيق دون رمز صحيح",
                        )
                        status.text = "رمز الأب غير صحيح"
                        pin.text.clear()
                    } else if (!prepareParentAuthorizedUninstall(prefs)) {
''',
    '''                setOnClickListener {
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        status.text = lockDelayText(remaining)
                        return@setOnClickListener
                    }
                    val candidate = pin.text.toString().trim()
                    if (!verifyPin(prefs, candidate)) {
                        val delay = registerLockPinFailure(
                            this@UninstallPinActivity,
                            prefs,
                            "محاولة حذف التطبيق دون رمز صحيح",
                        )
                        status.text = "رمز الأب غير صحيح. ${lockDelayText(delay)}"
                        pin.text.clear()
                    } else if (!prepareParentAuthorizedUninstall(prefs)) {
''',
    "uninstall PIN throttling",
)

# Add explicit hardening markers for CI auditing.
text += "\n// UNIFIED_SECURITY_HARDENING_V2\n"
path.write_text(text, encoding="utf-8")
print("Unified parental-control hardening applied successfully")
