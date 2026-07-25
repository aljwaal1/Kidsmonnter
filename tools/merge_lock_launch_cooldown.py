from pathlib import Path

NATIVE_PATH = Path("native/MainActivityV2.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: لم يتم العثور على المقطع المتوقع")
    return text.replace(old, new, 1)


source = NATIVE_PATH.read_text(encoding="utf-8")

source = replace_once(
    source,
    'private const val MAX_FAILED_ATTEMPTS = 50\n',
    'private const val MAX_FAILED_ATTEMPTS = 50\n'
    'private const val LOCK_LAUNCH_COOLDOWN_MS = 5_000L\n',
    "ثابت مهلة القفل",
)

source = replace_once(
    source,
    '    private var overlayWarningRecorded = false\n',
    '    private var overlayWarningRecorded = false\n'
    '    private var lastLockLaunchElapsedMs = 0L\n',
    "حالة آخر محاولة قفل",
)

source = replace_once(
    source,
    '''    private fun showLock() {
        if (!Settings.canDrawOverlays(this)) return
        try {
            startActivity(Intent(this, LockActivity::class.java).addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS
            ))
        } catch (_: Exception) {
            notifyWarning("انتهى وقت الهاتف، لكن تعذر فتح شاشة القفل")
        }
    }
''',
    '''    private fun showLock() {
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
''',
    "مهلة تشغيل شاشة القفل",
)

NATIVE_PATH.write_text(source, encoding="utf-8")
print("تم دمج مهلة محاولات إظهار شاشة القفل بأمان")
