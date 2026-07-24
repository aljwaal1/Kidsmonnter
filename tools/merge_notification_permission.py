from pathlib import Path

SOURCE = Path("native/MainActivityV2.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one {label} anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")

text = replace_once(
    text,
    "import android.app.*\n",
    "import android.Manifest\nimport android.app.*\n",
    "Manifest import",
)

helper_anchor = '''private fun Context.startMonitorServiceSafely() {
    val intent = Intent(this, MonitorService::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
}
'''
helper_replacement = helper_anchor + '''
private fun Activity.requestNotificationPermissionIfNeeded() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
    ) {
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7001)
    }
}
'''
text = replace_once(
    text,
    helper_anchor,
    helper_replacement,
    "notification permission helper",
)

start_anchor = '''                    startMonitorServiceSafely()
                    result.success(true)
                }
                "restartProtectionService" -> {
'''
start_replacement = '''                    requestNotificationPermissionIfNeeded()
                    startMonitorServiceSafely()
                    result.success(true)
                }
                "restartProtectionService" -> {
'''
text = replace_once(
    text,
    start_anchor,
    start_replacement,
    "startProtection notification permission request",
)

SOURCE.write_text(text, encoding="utf-8")
print("Notification permission request merged safely.")
