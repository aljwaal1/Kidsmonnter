from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
start = source.index("class LockActivity : Activity() {")
end = source.index("class KidsMonnterDeviceAdminReceiver", start)

replacement = r'''class LockActivity : Activity() {
    private val prefs by lazy { guardPrefs() }
    private val handler = Handler(Looper.getMainLooper())
    private var authorizedExit = false
    private val enteredPin = StringBuilder(6)
    private lateinit var pinDisplay: TextView
    private lateinit var statusView: TextView
    private lateinit var addTimeButton: Button
    private lateinit var unlockTodayButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configureDeviceOwnerPolicies()
        window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)
        if (!shouldRemainLocked()) { finish(); return }
        showImmersive()
        val dpm = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        if (dpm.isLockTaskPermitted(packageName)) try { startLockTask() } catch (_: Exception) {}
        setContentView(buildLockView())
    }

    override fun onResume() {
        super.onResume()
        showImmersive()
        if (!shouldRemainLocked()) exitLock()
    }

    override fun onPause() {
        super.onPause()
        if (!authorizedExit && shouldRemainLocked()) handler.postDelayed({
            if (!authorizedExit && shouldRemainLocked() && isScreenInteractive()) {
                try {
                    startActivity(Intent(this, LockActivity::class.java).addFlags(
                        Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP
                    ))
                } catch (_: Exception) {}
            }
        }, 800L)
    }

    private fun isScreenInteractive(): Boolean =
        (getSystemService(POWER_SERVICE) as PowerManager).isInteractive

    private fun shouldRemainLocked(): Boolean {
        if (!prefs.getBoolean("enabled", false)) return false
        if (prefs.getString("unlocked_date", "") == today()) return false
        return prefs.getInt("used_seconds", 0) >= prefs.getInt("daily_minutes", 60).coerceAtLeast(1) * 60
    }

    private fun showImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun buildLockView(): View {
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

        pinDisplay = TextView(this).apply {
            text = "○ ○ ○ ○ ○ ○"
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(12, 18, 12, 18)
            setBackgroundColor(Color.rgb(38, 62, 58))
            contentDescription = "رمز ولي الأمر، ست خانات"
        }
        root.addView(pinDisplay, LinearLayout.LayoutParams(-1, -2))

        statusView = TextView(this).apply {
            setTextColor(Color.rgb(255, 180, 170))
            gravity = Gravity.CENTER
            setPadding(0, 10, 0, 10)
        }
        root.addView(statusView, LinearLayout.LayoutParams(-1, -2))

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
                        "مسح" -> enteredPin.clear()
                        "⌫" -> if (enteredPin.isNotEmpty()) enteredPin.deleteCharAt(enteredPin.lastIndex)
                        else -> if (enteredPin.length < 6) enteredPin.append(label)
                    }
                    statusView.text = ""
                    refreshPinUi()
                }
            }, GridLayout.LayoutParams().apply {
                width = 0
                height = GridLayout.LayoutParams.WRAP_CONTENT
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
            })
        }
        root.addView(keypad, LinearLayout.LayoutParams(-1, -2))

        addTimeButton = Button(this).apply {
            text = "إضافة 15 دقيقة"
            isEnabled = false
            setOnClickListener { unlockWithPin(addTime = true) }
        }
        root.addView(addTimeButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })

        unlockTodayButton = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            isEnabled = false
            setOnClickListener { unlockWithPin(addTime = false) }
        }
        root.addView(unlockTodayButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(root, ScrollView.LayoutParams(-1, -2))
        }
        refreshPinUi()
        return scroll
    }

    private fun refreshPinUi() {
        val dots = MutableList(6) { index -> if (index < enteredPin.length) "●" else "○" }
        pinDisplay.text = dots.joinToString(" ")
        val ready = enteredPin.length == 6
        addTimeButton.isEnabled = ready
        unlockTodayButton.isEnabled = ready
    }

    private fun unlockWithPin(addTime: Boolean) {
        val pin = enteredPin.toString()
        val source = if (addTime) "فتح القفل وإضافة 15 دقيقة" else "فتح الهاتف لبقية اليوم"
        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, source)
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
            enteredPin.clear()
            refreshPinUi()
            return
        }

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

    private fun exitLock() {
        authorizedExit = true
        handler.removeCallbacksAndMessages(null)
        try { stopLockTask() } catch (_: Exception) {}
        finishAndRemoveTask()
        overridePendingTransition(0, 0)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() = Unit
}

'''

path.write_text(source[:start] + replacement + source[end:], encoding="utf-8")
print("Safe internal lock keypad merged")
