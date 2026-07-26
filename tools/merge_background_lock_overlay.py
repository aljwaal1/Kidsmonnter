from pathlib import Path

NATIVE_PATH = Path("native/MainActivityV2.kt")
MARKER = "BACKGROUND_LOCK_OVERLAY_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: لم يتم العثور على المقطع المتوقع")
    return text.replace(old, new, 1)


source = NATIVE_PATH.read_text(encoding="utf-8")
if MARKER in source:
    print("قفل الخلفية التلقائي مدمج مسبقاً")
    raise SystemExit(0)

source = replace_once(
    source,
    "import android.graphics.Color\n",
    "import android.graphics.Color\nimport android.graphics.PixelFormat\n",
    "استيراد تنسيق نافذة القفل",
)

source = replace_once(
    source,
    "    private var lastLockLaunchElapsedMs = 0L\n",
    "    private var lastLockLaunchElapsedMs = 0L\n"
    "    private var lockOverlayView: View? = null\n"
    "    private var lockWindowManager: WindowManager? = null\n"
    "    private val lockOverlayPin = StringBuilder(6)\n"
    "    private var lockOverlayPinDisplay: TextView? = null\n"
    "    private var lockOverlayStatus: TextView? = null\n"
    "    private var lockOverlayActionButtons: List<Button> = emptyList()\n",
    "حالة نافذة القفل التلقائي",
)

source = replace_once(
    source,
    """    override fun onDestroy() {
        accountElapsedUsage()
        handler.removeCallbacks(ticker)
""",
    """    override fun onDestroy() {
        accountElapsedUsage()
        dismissLockOverlay()
        handler.removeCallbacks(ticker)
""",
    "تنظيف نافذة القفل عند إيقاف الخدمة",
)

old_lock = """    private fun enforceLockIfNeeded() {
        if (screenOn && isTimeFinished()) showLock()
    }

    private fun showLock() {
        if (!Settings.canDrawOverlays(this)) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastLockLaunchElapsedMs < LOCK_LAUNCH_COOLDOWN_MS) return
        lastLockLaunchElapsedMs = now
        try {
            startActivity(Intent(this, LockActivity::class.java).addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS
            ))
        } catch (_: Exception) {
            notifyWarning("انتهى وقت الهاتف، لكن تعذر فتح شاشة القفل")
        }
    }
"""

new_lock = """    // BACKGROUND_LOCK_OVERLAY_MARKER: the service owns the lock UI so Android does not
    // need to start an Activity while the application is in the background.
    private fun enforceLockIfNeeded() {
        if (screenOn && isTimeFinished()) showLock() else dismissLockOverlay()
    }

    private fun showLock() {
        if (lockOverlayView != null) return
        if (!Settings.canDrawOverlays(this)) {
            notifyWarning("انتهى وقت الهاتف. فعّل صلاحية الظهور فوق التطبيقات ليعمل القفل تلقائياً")
            return
        }

        val now = SystemClock.elapsedRealtime()
        if (now - lastLockLaunchElapsedMs < LOCK_LAUNCH_COOLDOWN_MS) return
        lastLockLaunchElapsedMs = now

        try {
            configureDeviceOwnerPolicies()
            val manager = getSystemService(WINDOW_SERVICE) as WindowManager
            val view = buildBackgroundLockOverlay()
            val overlayType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            }
            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                overlayType,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_FULLSCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.OPAQUE,
            ).apply {
                gravity = Gravity.TOP or Gravity.START
            }
            manager.addView(view, params)
            lockWindowManager = manager
            lockOverlayView = view
            refreshBackgroundLockPinUi()
        } catch (_: Exception) {
            dismissLockOverlay()
            notifyWarning("انتهى وقت الهاتف، لكن تعذر إنشاء شاشة القفل التلقائية")
        }
    }

    private fun buildBackgroundLockOverlay(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(32, 32, 32, 32)
            setBackgroundColor(Color.rgb(25, 42, 39))
        }
        root.addView(TextView(this).apply {
            text = "انتهى وقت الهاتف اليوم"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(-1, -2))
        root.addView(TextView(this).apply {
            text = "أدخل رمز ولي الأمر من لوحة الأرقام الآمنة."
            textSize = 17f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 16, 0, 20)
        }, LinearLayout.LayoutParams(-1, -2))

        lockOverlayPinDisplay = TextView(this).apply {
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(12, 18, 12, 18)
            setBackgroundColor(Color.rgb(38, 62, 58))
            contentDescription = "رمز ولي الأمر، ست خانات"
        }
        root.addView(lockOverlayPinDisplay, LinearLayout.LayoutParams(-1, -2))

        lockOverlayStatus = TextView(this).apply {
            setTextColor(Color.rgb(255, 180, 170))
            gravity = Gravity.CENTER
            setPadding(0, 10, 0, 10)
        }
        root.addView(lockOverlayStatus, LinearLayout.LayoutParams(-1, -2))

        val keypad = GridLayout(this).apply {
            columnCount = 3
            rowCount = 4
            useDefaultMargins = true
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "مسح", "0", "⌫").forEach { label ->
            keypad.addView(Button(this).apply {
                text = label
                textSize = if (label.length == 1) 22f else 16f
                minHeight = 64
                setOnClickListener {
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
            }, GridLayout.LayoutParams().apply {
                width = 0
                height = GridLayout.LayoutParams.WRAP_CONTENT
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
            })
        }
        root.addView(keypad, LinearLayout.LayoutParams(-1, -2))

        val addTime = Button(this).apply {
            text = "إضافة 15 دقيقة"
            setOnClickListener { addTimeFromBackgroundLock() }
        }
        val unlockToday = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            setOnClickListener { unlockTodayFromBackgroundLock() }
        }
        val stopProtection = Button(this).apply {
            text = "إيقاف الحماية"
            setOnClickListener { stopProtectionFromBackgroundLock() }
        }
        lockOverlayActionButtons = listOf(addTime, unlockToday, stopProtection)
        root.addView(addTime, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })
        root.addView(unlockToday, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
        root.addView(stopProtection, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        return ScrollView(this).apply {
            isFillViewport = true
            addView(root, FrameLayout.LayoutParams(-1, -2))
        }
    }

    private fun refreshBackgroundLockPinUi() {
        val dots = MutableList(6) { index -> if (index < lockOverlayPin.length) "●" else "○" }
        lockOverlayPinDisplay?.text = dots.joinToString(" ")
        val ready = lockOverlayPin.length == 6
        lockOverlayActionButtons.forEach { it.isEnabled = ready }
    }

    private fun verifyBackgroundLockPin(source: String): Boolean {
        if (verifyPin(prefs, lockOverlayPin.toString())) return true
        recordFailedAttempt(this, prefs, source)
        lockOverlayStatus?.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
        lockOverlayPin.clear()
        refreshBackgroundLockPinUi()
        return false
    }

    private fun addTimeFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح القفل وإضافة 15 دقيقة")) return
        val used = prefs.getInt("used_seconds", 0)
        val saved = prefs.edit()
            .putInt("used_seconds", (used - 900).coerceAtLeast(0))
            .remove("unlocked_date")
            .commit()
        if (!saved) {
            lockOverlayStatus?.text = "تعذر حفظ الوقت الإضافي. حاول مرة أخرى."
            return
        }
        dismissLockOverlay()
    }

    private fun unlockTodayFromBackgroundLock() {
        if (!verifyBackgroundLockPin("فتح الهاتف لبقية اليوم")) return
        if (!prefs.edit().putString("unlocked_date", today()).commit()) {
            lockOverlayStatus?.text = "تعذر حفظ أمر الفتح. حاول مرة أخرى."
            return
        }
        dismissLockOverlay()
    }

    private fun stopProtectionFromBackgroundLock() {
        if (!verifyBackgroundLockPin("إيقاف الحماية من شاشة القفل")) return
        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            lockOverlayStatus?.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }
        releaseDeviceOwnerPolicies()
        dismissLockOverlay()
        stopSelf()
    }

    private fun dismissLockOverlay() {
        val view = lockOverlayView
        if (view != null) {
            try {
                (lockWindowManager ?: getSystemService(WINDOW_SERVICE) as WindowManager)
                    .removeViewImmediate(view)
            } catch (_: Exception) {}
        }
        lockOverlayView = null
        lockWindowManager = null
        lockOverlayPin.clear()
        lockOverlayPinDisplay = null
        lockOverlayStatus = null
        lockOverlayActionButtons = emptyList()
    }
"""

source = replace_once(source, old_lock, new_lock, "نافذة القفل التلقائي من خدمة الخلفية")

NATIVE_PATH.write_text(source, encoding="utf-8")
print("تم دمج نافذة القفل التلقائي التي تعمل دون فتح التطبيق")
