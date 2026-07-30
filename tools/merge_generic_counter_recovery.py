from pathlib import Path

NATIVE = Path("native/MainActivityV2.kt")
MARKER = "GENERIC_COUNTER_RECOVERY_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


native = NATIVE.read_text(encoding="utf-8")

if MARKER not in native:
    native = replace_once(
        native,
        'private const val LAST_TICK_KEY = "last_tick_elapsed_ms"\n',
        'private const val LAST_TICK_KEY = "last_tick_elapsed_ms"\n'
        'private const val LAST_USAGE_ELIGIBLE_KEY = "last_usage_eligible"\n',
        "حالة أهلية احتساب الاستخدام",
    )

    native = replace_once(
        native,
        '''                    Intent.ACTION_SCREEN_OFF -> {
                        accountElapsedUsage()
                        screenOn = false
                        resetClockAnchor()
                    }
                    Intent.ACTION_SCREEN_ON, Intent.ACTION_USER_PRESENT -> {
                        screenOn = true
                        resetClockAnchor()
                        enforceLockIfNeeded()
                    }
''',
        '''                    Intent.ACTION_SCREEN_OFF -> {
                        accountElapsedUsage()
                        screenOn = false
                        resetClockAnchor("screen_off")
                    }
                    Intent.ACTION_SCREEN_ON -> {
                        screenOn = true
                        resetClockAnchor("screen_on_locked")
                        enforceLockIfNeeded()
                    }
                    Intent.ACTION_USER_PRESENT -> {
                        screenOn = true
                        resetClockAnchor("user_present")
                        enforceLockIfNeeded()
                    }
''',
        "أحداث الشاشة العامة للعداد",
    )

    native = replace_once(
        native,
        '''                } else {
                    resetClockAnchor()
                }
''',
        '''                } else {
                    resetClockAnchor("protection_disabled", logReason = false)
                }
''',
        "تثبيت مرساة العداد عند تعطيل الحماية",
    )

    native = replace_once(
        native,
        '''        resetClockAnchor()
        scheduleMonitorWatchdog()
''',
        '''        resetIfNewDay()
        recoverElapsedUsageIfNeeded("service_created")
        scheduleMonitorWatchdog()
''',
        "استعادة العداد عند إنشاء الخدمة",
    )

    native = replace_once(
        native,
        '''        try {
            resetClockAnchor()
            appendGuardLog(
''',
        '''        try {
            recoverElapsedUsageIfNeeded("service_start_command")
            appendGuardLog(
''',
        "عدم تصفير العداد عند أوامر إعادة التشغيل",
    )

    old_counter = '''    private fun resetClockAnchor() {
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

        val limit = prefs.getInt("daily_minutes", 10).coerceAtLeast(1) * 60
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
'''
    new_counter = '''    // GENERIC_COUNTER_RECOVERY_MARKER
    private fun isUsageEligibleNow(): Boolean {
        if (!screenOn) return false
        val keyguard = getSystemService(KEYGUARD_SERVICE) as KeyguardManager
        return !keyguard.isDeviceLocked
    }

    private fun resetClockAnchor(
        reason: String = "unspecified",
        logReason: Boolean = true,
    ) {
        val now = SystemClock.elapsedRealtime()
        val eligible = isUsageEligibleNow()
        prefs.edit()
            .putLong(LAST_TICK_KEY, now)
            .putBoolean(LAST_USAGE_ELIGIBLE_KEY, eligible)
            .apply()
        if (logReason) {
            appendGuardLog(
                "COUNTER_ANCHOR_RESET_REASON",
                "reason=$reason elapsed=$now screenOn=$screenOn eligible=$eligible",
            )
        }
    }

    private fun applyElapsedUsage(elapsedSeconds: Int, eventName: String, reason: String) {
        if (elapsedSeconds <= 0) return
        val limit = prefs.getInt("daily_minutes", 10).coerceAtLeast(1) * 60
        val before = prefs.getInt("used_seconds", 0).coerceAtLeast(0)
        val after = (before + elapsedSeconds).coerceAtMost(limit)
        if (after == before) return

        prefs.edit().putInt("used_seconds", after).commit()
        appendGuardLog(
            eventName,
            "reason=$reason before=$before after=$after elapsed=$elapsedSeconds limit=$limit",
        )
        if (before < limit - 300 && after >= limit - 300) {
            notifyWarning("تبقّى 5 دقائق من وقت الهاتف")
        }
        if (before < limit - 60 && after >= limit - 60) {
            notifyWarning("تبقّت دقيقة واحدة من وقت الهاتف")
        }
    }

    private fun recoverElapsedUsageIfNeeded(reason: String) {
        val now = SystemClock.elapsedRealtime()
        val previousAnchor = prefs.getLong(LAST_TICK_KEY, 0L)
        val wasEligible = prefs.getBoolean(LAST_USAGE_ELIGIBLE_KEY, false)
        val eligibleNow = isUsageEligibleNow()

        if (previousAnchor <= 0L || previousAnchor > now) {
            resetClockAnchor("$reason-invalid_anchor")
            return
        }
        if (!prefs.getBoolean("enabled", false) ||
            prefs.getString("unlocked_date", "") == today() ||
            !wasEligible ||
            !eligibleNow
        ) {
            resetClockAnchor("$reason-not_eligible")
            return
        }

        val elapsedSeconds = ((now - previousAnchor) / 1000L).toInt().coerceAtLeast(0)
        prefs.edit()
            .putLong(LAST_TICK_KEY, now)
            .putBoolean(LAST_USAGE_ELIGIBLE_KEY, eligibleNow)
            .apply()
        applyElapsedUsage(elapsedSeconds, "COUNTER_RECOVERED", reason)
    }

    private fun accountElapsedUsage() {
        val now = SystemClock.elapsedRealtime()
        val previousAnchor = prefs.getLong(LAST_TICK_KEY, 0L)
        val eligibleNow = isUsageEligibleNow()
        prefs.edit()
            .putLong(LAST_TICK_KEY, now)
            .putBoolean(LAST_USAGE_ELIGIBLE_KEY, eligibleNow)
            .apply()

        if (!prefs.getBoolean("enabled", false) || !eligibleNow) return
        if (prefs.getString("unlocked_date", "") == today()) return
        if (previousAnchor <= 0L || previousAnchor > now) return

        val elapsedSeconds = ((now - previousAnchor) / 1000L).toInt().coerceAtLeast(0)
        applyElapsedUsage(elapsedSeconds, "USAGE_ACCOUNTED", "ticker")
    }
'''
    native = replace_once(native, old_counter, new_counter, "محرك استعادة العداد")

    native = replace_once(
        native,
        '''        overlayWarningRecorded = false
        resetClockAnchor()
''',
        '''        overlayWarningRecorded = false
        resetClockAnchor("new_day")
''',
        "مرساة بداية اليوم الجديد",
    )

NATIVE.write_text(native, encoding="utf-8")
print("Generic counter recovery merged")
