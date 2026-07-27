from pathlib import Path

NATIVE = Path("native/MainActivityV2.kt")
MANIFEST = Path("native/AndroidManifest.xml")
MARKER = "EXTREME_LOCK_HARDENING_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"تعذر دمج {label}: بداية المقطع غير موجودة")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"تعذر دمج {label}: نهاية المقطع غير موجودة")
    return text[:start_index] + replacement + text[end_index:]


native = NATIVE.read_text(encoding="utf-8")
if MARKER in native:
    print("Extreme lock hardening already merged")
    raise SystemExit(0)

native = replace_once(
    native,
    "import android.graphics.PixelFormat\n",
    "import android.graphics.PixelFormat\nimport android.graphics.Rect\n",
    "استيراد حدود إيماءات النظام",
)
native = replace_once(
    native,
    "import android.view.Gravity\n",
    "import android.view.Gravity\nimport android.view.KeyEvent\nimport android.view.WindowInsets\nimport android.view.WindowInsetsController\n",
    "استيراد أدوات القفل الكامل",
)
native = replace_once(
    native,
    'private const val WAKE_LOCK_TIMEOUT_MS = 12_000L\n',
    'private const val WAKE_LOCK_TIMEOUT_MS = 12_000L\n'
    'private const val LOCK_ACTIVITY_LAUNCH_COOLDOWN_MS = 2_000L\n'
    'private const val LOCK_ACTION_GRACE_MS = 3_000L\n'
    'private const val PIN_FAILURE_STREAK_KEY = "lock_pin_failure_streak"\n'
    'private const val PIN_BLOCK_UNTIL_MS_KEY = "lock_pin_block_until_ms"\n'
    'private const val MAX_PIN_BLOCK_MS = 60_000L\n',
    "ثوابت القفل الصارم",
)

helpers = r'''// EXTREME_LOCK_HARDENING_MARKER
private fun lockPinBlockRemainingMs(prefs: SharedPreferences): Long {
    val until = prefs.getLong(PIN_BLOCK_UNTIL_MS_KEY, 0L)
    if (until <= 0L) return 0L
    val remaining = until - System.currentTimeMillis()
    if (remaining <= 0L || remaining > MAX_PIN_BLOCK_MS) {
        prefs.edit().remove(PIN_BLOCK_UNTIL_MS_KEY).apply()
        return 0L
    }
    return remaining
}

private fun registerLockPinFailure(
    context: Context,
    prefs: SharedPreferences,
    source: String,
): Long {
    val streak = (prefs.getInt(PIN_FAILURE_STREAK_KEY, 0) + 1).coerceAtMost(50)
    val delayMs = when {
        streak >= 10 -> 60_000L
        streak >= 5 -> 15_000L
        else -> 2_000L
    }
    prefs.edit()
        .putInt(PIN_FAILURE_STREAK_KEY, streak)
        .putLong(PIN_BLOCK_UNTIL_MS_KEY, System.currentTimeMillis() + delayMs)
        .commit()
    recordFailedAttempt(context, prefs, "$source (محاولة متتالية $streak)")
    return delayMs
}

private fun clearLockPinFailureState(prefs: SharedPreferences) {
    prefs.edit()
        .remove(PIN_FAILURE_STREAK_KEY)
        .remove(PIN_BLOCK_UNTIL_MS_KEY)
        .apply()
}

private fun lockDelayText(delayMs: Long): String =
    "انتظر ${((delayMs + 999L) / 1000L).coerceAtLeast(1L)} ثانية ثم حاول مرة أخرى."

private fun Context.disableProtectionFailOpen(reason: String) {
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

'''
native = replace_once(
    native,
    "private fun Context.startMonitorServiceSafely() {\n",
    helpers + "private fun Context.startMonitorServiceSafely() {\n",
    "صمام الأمان وتأخير محاولات PIN",
)

policy = r'''private fun Context.configureDeviceOwnerPolicies(): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return false
    return try {
        val admin = deviceAdminComponent()
        manager.setLockTaskPackages(admin, arrayOf(packageName))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            manager.setLockTaskFeatures(admin, DevicePolicyManager.LOCK_TASK_FEATURE_NONE)
        }
        manager.setUninstallBlocked(admin, packageName, true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, true)
        }
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_APPLIED")
        true
    } catch (error: SecurityException) {
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_FAILED", error = error)
        false
    }
}

'''
native = replace_between(
    native,
    "private fun Context.configureDeviceOwnerPolicies() {",
    "private fun Context.releaseDeviceOwnerPolicies() {",
    policy,
    "سياسات Device Owner الصارمة",
)

native = replace_once(
    native,
    "    private var lastDiagnosticHeartbeatElapsedMs = 0L\n",
    "    private var lastDiagnosticHeartbeatElapsedMs = 0L\n"
    "    private var lastLockActivityLaunchElapsedMs = 0L\n"
    "    private var lockActionInProgress = false\n"
    "    private var lockActionGraceUntilElapsedMs = 0L\n",
    "حالة جلسة القفل الصارمة",
)

enforce = r'''    private fun enforceLockIfNeeded() {
        if (!prefs.getBoolean("enabled", false)) {
            dismissLockOverlay()
            return
        }
        if (!hasStoredPin(prefs)) {
            appendGuardLog("LOCK_ABORTED_INVALID_PIN_STATE")
            disableProtectionFailOpen("missing_or_corrupt_parent_pin")
            dismissLockOverlay()
            stopSelf()
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (!isTimeFinished()) {
            if (!lockActionInProgress && now >= lockActionGraceUntilElapsedMs) {
                dismissLockOverlay()
            }
            return
        }
        if (lockActionInProgress || now < lockActionGraceUntilElapsedMs) return

        showLock()
        if (screenOn) launchLockActivityIfDeviceOwner()
    }

    private fun launchLockActivityIfDeviceOwner() {
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
native = replace_between(
    native,
    "    private fun enforceLockIfNeeded() {",
    "    private fun showLock() {",
    enforce,
    "القفل المزدوج",
)

native = replace_once(
    native,
    "            val view = buildBackgroundLockOverlay()\n",
    "            val view = buildBackgroundLockOverlay().apply {\n"
    "                systemUiVisibility = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or\n"
    "                    View.SYSTEM_UI_FLAG_FULLSCREEN or\n"
    "                    View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or\n"
    "                    View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or\n"
    "                    View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or\n"
    "                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE\n"
    "                isFocusable = true\n"
    "                isFocusableInTouchMode = true\n"
    "                setOnKeyListener { _, keyCode, _ ->\n"
    "                    keyCode == KeyEvent.KEYCODE_BACK ||\n"
    "                        keyCode == KeyEvent.KEYCODE_MENU ||\n"
    "                        keyCode == KeyEvent.KEYCODE_SEARCH ||\n"
    "                        keyCode == KeyEvent.KEYCODE_ASSIST ||\n"
    "                        keyCode == KeyEvent.KEYCODE_APP_SWITCH\n"
    "                }\n"
    "            }\n",
    "تركيز نافذة القفل ومنع مفاتيح التجاوز",
)
native = replace_once(
    native,
    "                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or\n"
    "                    WindowManager.LayoutParams.FLAG_FULLSCREEN or\n"
    "                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,\n",
    "                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or\n"
    "                    WindowManager.LayoutParams.FLAG_FULLSCREEN or\n"
    "                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or\n"
    "                    WindowManager.LayoutParams.FLAG_SECURE or\n"
    "                    WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM,\n",
    "رايات نافذة القفل الصارمة",
)
native = replace_once(
    native,
    "            ).apply {\n                gravity = Gravity.TOP or Gravity.START\n            }\n",
    "            ).apply {\n"
    "                gravity = Gravity.TOP or Gravity.START\n"
    "                softInputMode = WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN\n"
    "                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {\n"
    "                    layoutInDisplayCutoutMode =\n"
    "                        WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES\n"
    "                }\n"
    "            }\n",
    "تغطية الحواف وإخفاء لوحة المفاتيح",
)
native = replace_once(
    native,
    "            lockOverlayView = view\n            refreshBackgroundLockPinUi()\n",
    "            lockOverlayView = view\n"
    "            view.post {\n"
    "                view.requestFocus()\n"
    "                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && view.width > 0 && view.height > 0) {\n"
    "                    view.systemGestureExclusionRects = listOf(Rect(0, 0, view.width, view.height))\n"
    "                }\n"
    "            }\n"
    "            refreshBackgroundLockPinUi()\n",
    "استبعاد إيماءات الحواف",
)
native = replace_once(
    native,
    "            setBackgroundColor(Color.rgb(25, 42, 39))\n        }\n",
    "            setBackgroundColor(Color.rgb(25, 42, 39))\n"
    "            isClickable = true\n"
    "            isFocusable = true\n"
    "            isFocusableInTouchMode = true\n"
    "            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES\n"
    "        }\n",
    "جذر نافذة القفل الملتقط للمس",
)

old_overlay_click = r'''                setOnClickListener {
                    when (label) {
                        "مسح" -> lockOverlayPin.clear()
                        "⌫" -> if (lockOverlayPin.isNotEmpty()) {
                            lockOverlayPin.deleteCharAt(lockOverlayPin.length - 1)
                        }
                        else -> if (lockOverlayPin.length < 6) lockOverlayPin.append(label)
                    }
                    lockOverlayStatus?.text = ""
                    refreshBackgroundLockPinUi()
                }
'''
new_overlay_click = r'''                setOnClickListener {
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        lockOverlayStatus?.text = lockDelayText(remaining)
                        return@setOnClickListener
                    }
                    when (label) {
                        "مسح" -> lockOverlayPin.clear()
                        "⌫" -> if (lockOverlayPin.isNotEmpty()) {
                            lockOverlayPin.deleteCharAt(lockOverlayPin.length - 1)
                        }
                        else -> if (lockOverlayPin.length < 6) lockOverlayPin.append(label)
                    }
                    lockOverlayStatus?.text = ""
                    refreshBackgroundLockPinUi()
                }
'''
native = replace_once(native, old_overlay_click, new_overlay_click, "تأخير لوحة PIN في النافذة")

verify_overlay = r'''    private fun verifyBackgroundLockPin(source: String): Boolean {
        val remaining = lockPinBlockRemainingMs(prefs)
        if (remaining > 0L) {
            lockOverlayStatus?.text = lockDelayText(remaining)
            return false
        }
        if (verifyPin(prefs, lockOverlayPin.toString())) {
            clearLockPinFailureState(prefs)
            return true
        }
        val delay = registerLockPinFailure(this, prefs, source)
        lockOverlayStatus?.text = "رمز ولي الأمر غير صحيح. ${lockDelayText(delay)}"
        lockOverlayPin.clear()
        refreshBackgroundLockPinUi()
        return false
    }

'''
native = replace_between(
    native,
    "    private fun verifyBackgroundLockPin(source: String): Boolean {",
    "    private fun addTimeFromBackgroundLock() {",
    verify_overlay,
    "التحقق الصارم من PIN في النافذة",
)

actions = r'''    private fun completeAuthorizedOverlayAction() {
        lockActionGraceUntilElapsedMs = SystemClock.elapsedRealtime() + LOCK_ACTION_GRACE_MS
        dismissLockOverlay()
        lockActionInProgress = false
    }

    private fun addTimeFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح القفل وإضافة 15 دقيقة")) return
        lockActionInProgress = true
        val used = prefs.getInt("used_seconds", 0)
        val saved = prefs.edit()
            .putInt("used_seconds", (used - 900).coerceAtLeast(0))
            .remove("unlocked_date")
            .commit()
        if (!saved) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر حفظ الوقت الإضافي. حاول مرة أخرى."
            return
        }
        resetClockAnchor()
        completeAuthorizedOverlayAction()
    }

    private fun unlockTodayFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح الهاتف لبقية اليوم")) return
        lockActionInProgress = true
        if (!prefs.edit().putString("unlocked_date", today()).commit()) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر حفظ أمر الفتح. حاول مرة أخرى."
            return
        }
        completeAuthorizedOverlayAction()
    }

    private fun stopProtectionFromBackgroundLock() {
        if (!verifyBackgroundLockPin("إيقاف الحماية من شاشة القفل")) return
        lockActionInProgress = true
        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            lockActionInProgress = false
            lockOverlayStatus?.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }
        clearLockPinFailureState(prefs)
        syncBootProtectionState(false)
        releaseDeviceOwnerPolicies()
        dismissLockOverlay()
        stopSelf()
    }

'''
native = replace_between(
    native,
    "    private fun addTimeFromBackgroundLock() {",
    "    private fun dismissLockOverlay() {",
    actions,
    "إجراءات الفتح الذرية",
)

dismiss = r'''    private fun dismissLockOverlay() {
        val view = lockOverlayView
        val manager = lockWindowManager
        lockOverlayView = null
        lockWindowManager = null
        lockOverlayPinDisplay = null
        lockOverlayStatus = null
        lockOverlayActionButtons = emptyList()
        lockOverlayPin.clear()
        if (view != null) {
            try {
                (manager ?: getSystemService(WINDOW_SERVICE) as WindowManager)
                    .removeViewImmediate(view)
            } catch (error: Exception) {
                appendGuardLog("LOCK_OVERLAY_REMOVE_FAILED", error = error)
            }
        }
    }

'''
native = replace_between(
    native,
    "    private fun dismissLockOverlay() {",
    "    private fun monitorOverlayPermission() {",
    dismiss,
    "إزالة نافذة القفل دون سباق",
)

lifecycle = r'''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!hasStoredPin(prefs)) {
            disableProtectionFailOpen("lock_activity_missing_or_corrupt_parent_pin")
            finish()
            return
        }
        configureDeviceOwnerPolicies()
        window.addFlags(
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_FULLSCREEN or
                WindowManager.LayoutParams.FLAG_SECURE,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) setShowWhenLocked(true)
        if (!shouldRemainLocked()) { finish(); return }
        setContentView(buildLockView())
        reassertStrictLock()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        reassertStrictLock()
    }

    override fun onResume() {
        super.onResume()
        reassertStrictLock()
    }

    override fun onPause() {
        super.onPause()
        scheduleLockReassert()
    }

    override fun onStop() {
        super.onStop()
        scheduleLockReassert()
    }

    override fun onUserLeaveHint() {
        scheduleLockReassert()
        super.onUserLeaveHint()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) reassertStrictLock() else scheduleLockReassert()
    }

    override fun onDestroy() {
        if (!authorizedExit && shouldRemainLocked()) {
            try { startMonitorServiceSafely() } catch (_: Exception) {}
        }
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun scheduleLockReassert() {
        if (authorizedExit || !shouldRemainLocked()) return
        handler.removeCallbacksAndMessages(null)
        handler.postDelayed({
            if (!authorizedExit && shouldRemainLocked() && isScreenInteractive()) {
                try {
                    startActivity(
                        Intent(this, LockActivity::class.java).addFlags(
                            Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or
                                Intent.FLAG_ACTIVITY_SINGLE_TOP or
                                Intent.FLAG_ACTIVITY_NO_ANIMATION,
                        ),
                    )
                    reassertStrictLock()
                } catch (error: Exception) {
                    appendGuardLog("LOCK_ACTIVITY_SELF_REASSERT_FAILED", error = error)
                }
            }
        }, 250L)
    }

    private fun reassertStrictLock() {
        if (!shouldRemainLocked()) {
            exitLock()
            return
        }
        configureDeviceOwnerPolicies()
        showImmersive()
        val dpm = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        if (dpm.isLockTaskPermitted(packageName)) {
            try { startLockTask() } catch (error: Exception) {
                appendGuardLog("LOCK_TASK_START_FAILED", error = error)
            }
        }
    }

'''
native = replace_between(
    native,
    "    override fun onCreate(savedInstanceState: Bundle?) {",
    "    private fun isScreenInteractive(): Boolean =",
    lifecycle,
    "دورة حياة شاشة القفل الصارمة",
)

show_immersive = r'''    private fun showImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.insetsController?.let { controller ->
                controller.hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
                controller.systemBarsBehavior =
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        }
    }

'''
native = replace_between(
    native,
    "    private fun showImmersive() {",
    "    private fun buildLockView(): View {",
    show_immersive,
    "إخفاء شريطي النظام",
)

old_activity_click = r'''                setOnClickListener {
                    when (label) {
                        "مسح" -> enteredPin.clear()
                        "⌫" -> if (enteredPin.isNotEmpty()) enteredPin.deleteCharAt(enteredPin.lastIndex)
                        else -> if (enteredPin.length < 6) enteredPin.append(label)
                    }
                    statusView.text = ""
                    refreshPinUi()
                }
'''
new_activity_click = r'''                setOnClickListener {
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        statusView.text = lockDelayText(remaining)
                        return@setOnClickListener
                    }
                    when (label) {
                        "مسح" -> enteredPin.clear()
                        "⌫" -> if (enteredPin.isNotEmpty()) enteredPin.deleteCharAt(enteredPin.lastIndex)
                        else -> if (enteredPin.length < 6) enteredPin.append(label)
                    }
                    statusView.text = ""
                    refreshPinUi()
                }
'''
native = replace_once(native, old_activity_click, new_activity_click, "تأخير لوحة PIN في النشاط")

activity_actions = r'''    private fun verifyEnteredPin(source: String): Boolean {
        val remaining = lockPinBlockRemainingMs(prefs)
        if (remaining > 0L) {
            statusView.text = lockDelayText(remaining)
            return false
        }
        val pin = enteredPin.toString()
        if (verifyPin(prefs, pin)) {
            clearLockPinFailureState(prefs)
            return true
        }
        val delay = registerLockPinFailure(this, prefs, source)
        statusView.text = "رمز ولي الأمر غير صحيح. ${lockDelayText(delay)}"
        enteredPin.clear()
        refreshPinUi()
        return false
    }

    private fun disableProtectionWithPin() {
        if (!verifyEnteredPin("إيقاف الحماية من شاشة القفل")) return
        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            statusView.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }

        clearLockPinFailureState(prefs)
        syncBootProtectionState(false)
        releaseDeviceOwnerPolicies()
        stopService(Intent(this, MonitorService::class.java))
        exitLock()
    }

    private fun unlockWithPin(addTime: Boolean) {
        val source = if (addTime) "فتح القفل وإضافة 15 دقيقة" else "فتح الهاتف لبقية اليوم"
        if (!verifyEnteredPin(source)) return

        val saved = if (addTime) {
            val used = prefs.getInt("used_seconds", 0)
            prefs.edit().putInt("used_seconds", (used - 900).coerceAtLeast(0)).commit()
        } else {
            prefs.edit().putString("unlocked_date", today()).commit()
        }
        if (!saved) {
            statusView.text = "تعذر حفظ أمر الفتح. حاول مرة أخرى."
            return
        }
        exitLock()
    }

'''
native = replace_between(
    native,
    "    private fun disableProtectionWithPin() {",
    "    private fun exitLock() {",
    activity_actions,
    "إجراءات PIN الموحدة في النشاط",
)

key_dispatch = r'''    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (shouldRemainLocked()) {
            when (event.keyCode) {
                KeyEvent.KEYCODE_BACK,
                KeyEvent.KEYCODE_MENU,
                KeyEvent.KEYCODE_SEARCH,
                KeyEvent.KEYCODE_ASSIST,
                KeyEvent.KEYCODE_APP_SWITCH -> return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

'''
native = replace_once(
    native,
    "    @Deprecated(\"Deprecated in Java\")\n    override fun onBackPressed() = Unit\n",
    key_dispatch + "    @Deprecated(\"Deprecated in Java\")\n    override fun onBackPressed() = Unit\n",
    "اعتراض مفاتيح التجاوز",
)

NATIVE.write_text(native, encoding="utf-8")

manifest = MANIFEST.read_text(encoding="utf-8")
manifest = replace_once(
    manifest,
    '            android:resizeableActivity="false"\n            android:screenOrientation="portrait"',
    '            android:resizeableActivity="false"\n'
    '            android:supportsPictureInPicture="false"\n'
    '            android:screenOrientation="portrait"\n'
    '            android:windowSoftInputMode="stateAlwaysHidden"',
    "منع النوافذ المتعددة وPicture-in-Picture",
)
MANIFEST.write_text(manifest, encoding="utf-8")

print("Extreme lock hardening merged")
