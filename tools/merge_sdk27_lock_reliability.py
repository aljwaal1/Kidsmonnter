from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
marker = "SDK27_RELIABLE_LOCK_MARKER"
if marker in source:
    print("SDK 27 reliable lock already merged")
    raise SystemExit(0)

old_call = '''        showLock()
        if (screenOn) launchLockActivityIfDeviceOwner()
'''
new_call = '''        appendGuardLog(
            "LOCK_TRIGGERED",
            "used=${prefs.getInt(\"used_seconds\", 0)} limit=${prefs.getInt(\"daily_minutes\", 60) * 60} sdk=${Build.VERSION.SDK_INT}",
        )
        showLock()
        if (screenOn) launchLockActivityReliably()
'''
if old_call not in source:
    raise SystemExit("تعذر تعديل استدعاء شاشة القفل")
source = source.replace(old_call, new_call, 1)

old_function = '''    private fun launchLockActivityIfDeviceOwner() {
        val policy = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        if (!policy.isDeviceOwnerApp(packageName)) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastLockActivityLaunchElapsedMs < LOCK_ACTIVITY_LAUNCH_COOLDOWN_MS) return
        lastLockActivityLaunchElapsedMs = now
        try {
            configureDeviceOwnerPolicies()
            startActivity(
                Intent(this, LockActivity::class.java).addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or
                        Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS or
                        Intent.FLAG_ACTIVITY_NO_ANIMATION,
                ),
            )
            appendGuardLog("LOCK_ACTIVITY_REASSERTED", "deviceOwner=true")
        } catch (error: Exception) {
            appendGuardLog("LOCK_ACTIVITY_REASSERT_FAILED", error = error)
        }
    }
'''
new_function = '''    // SDK27_RELIABLE_LOCK_MARKER
    private fun launchLockActivityReliably() {
        val policy = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val deviceOwner = policy.isDeviceOwnerApp(packageName)
        val legacyBackgroundLaunchAllowed = Build.VERSION.SDK_INT <= Build.VERSION_CODES.P
        if (!deviceOwner && !legacyBackgroundLaunchAllowed) {
            appendGuardLog(
                "LOCK_ACTIVITY_SKIPPED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=false overlayFallback=true",
            )
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (now - lastLockActivityLaunchElapsedMs < LOCK_ACTIVITY_LAUNCH_COOLDOWN_MS) return
        lastLockActivityLaunchElapsedMs = now
        try {
            if (deviceOwner) configureDeviceOwnerPolicies()
            startActivity(
                Intent(this, LockActivity::class.java).addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or
                        Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS or
                        Intent.FLAG_ACTIVITY_NO_ANIMATION,
                ),
            )
            appendGuardLog(
                "LOCK_ACTIVITY_STARTED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=$deviceOwner legacy=$legacyBackgroundLaunchAllowed",
            )
        } catch (error: Exception) {
            appendGuardLog(
                "LOCK_ACTIVITY_START_FAILED",
                "sdk=${Build.VERSION.SDK_INT} deviceOwner=$deviceOwner",
                error,
            )
            showLock()
        }
    }
'''
if old_function not in source:
    raise SystemExit("تعذر استبدال منطق تشغيل LockActivity")
source = source.replace(old_function, new_function, 1)

old_start = '''        try {
            resetClockAnchor()
            enforceLockIfNeeded()
'''
new_start = '''        try {
            resetClockAnchor()
            appendGuardLog(
                "LOCK_EVALUATION",
                "used=${prefs.getInt(\"used_seconds\", 0)} limit=${prefs.getInt(\"daily_minutes\", 60) * 60} finished=${isTimeFinished()} screenOn=$screenOn",
            )
            enforceLockIfNeeded()
'''
if old_start not in source:
    raise SystemExit("تعذر إضافة تشخيص تقييم القفل")
source = source.replace(old_start, new_start, 1)

path.write_text(source, encoding="utf-8")
print("SDK 27 reliable lock merged")
