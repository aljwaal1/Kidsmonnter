from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")

if "private fun disableProtectionWithPin()" in source:
    print("Emergency stop already merged")
    raise SystemExit(0)

required = [
    "private lateinit var unlockTodayButton: Button",
    "unlockTodayButton = Button(this).apply {",
    "private fun refreshPinUi() {",
    "private fun unlockWithPin(addTime: Boolean) {",
]
for marker in required:
    if marker not in source:
        raise RuntimeError(f"Safe lock keypad marker not found: {marker}")

source = source.replace(
    "private lateinit var unlockTodayButton: Button",
    "private lateinit var unlockTodayButton: Button\n    private lateinit var stopProtectionButton: Button",
    1,
)

unlock_block = '''        unlockTodayButton = Button(this).apply {
            text = "فتح الهاتف لبقية اليوم"
            isEnabled = false
            setOnClickListener { unlockWithPin(addTime = false) }
        }
        root.addView(unlockTodayButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
'''

stop_block = unlock_block + '''
        stopProtectionButton = Button(this).apply {
            text = "إيقاف الحماية"
            isEnabled = false
            setOnClickListener { disableProtectionWithPin() }
        }
        root.addView(stopProtectionButton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
'''

if unlock_block not in source:
    raise RuntimeError("Unlock-today button block not found")
source = source.replace(unlock_block, stop_block, 1)

source = source.replace(
    "unlockTodayButton.isEnabled = ready",
    "unlockTodayButton.isEnabled = ready\n        stopProtectionButton.isEnabled = ready",
    1,
)

marker = "    private fun unlockWithPin(addTime: Boolean) {"
emergency_function = '''    private fun disableProtectionWithPin() {
        val pin = enteredPin.toString()
        if (!verifyPin(prefs, pin)) {
            recordFailedAttempt(this, prefs, "إيقاف الحماية من شاشة القفل")
            statusView.text = "رمز ولي الأمر غير صحيح. حاول مرة أخرى."
            enteredPin.clear()
            refreshPinUi()
            return
        }

        val saved = prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .commit()
        if (!saved) {
            statusView.text = "تعذر إيقاف الحماية. حاول مرة أخرى."
            return
        }

        stopService(Intent(this, MonitorService::class.java))
        exitLock()
    }

'''
source = source.replace(marker, emergency_function + marker, 1)

path.write_text(source, encoding="utf-8")
print("Emergency stop merged into lock screen")
