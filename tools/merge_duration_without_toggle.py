from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MARKER = "DURATION_WITHOUT_PROTECTION_TOGGLE_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


flutter = FLUTTER.read_text(encoding="utf-8")
native = NATIVE.read_text(encoding="utf-8")

if MARKER not in flutter:
    old = '''        final wasEnabled = _status?.enabled == true;
        await _channel.invokeMethod('startProtection', {'minutes': minutes});
        if (!wasEnabled) {
          await _channel.invokeMethod('stopProtection', {'pin': pin});
        }
        await _refreshStatus();
'''
    new = '''        // DURATION_WITHOUT_PROTECTION_TOGGLE_MARKER
        await _channel.invokeMethod('setDailyMinutes', {
          'pin': pin,
          'minutes': minutes,
        });
        await _refreshStatus();
'''
    flutter = replace_once(flutter, old, new, "حفظ المدة دون تبديل الحماية")

if MARKER not in native:
    anchor = '''                "addTime" -> {
'''
    replacement = '''                // DURATION_WITHOUT_PROTECTION_TOGGLE_MARKER
                "setDailyMinutes" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    val minutes = (call.argument<Int>("minutes") ?: 10).coerceIn(1, 1440)
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "تغيير المدة اليومية")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        prefs.edit().putInt("daily_minutes", minutes).commit()
                        appendGuardLog(
                            "DAILY_MINUTES_UPDATED",
                            "minutes=$minutes protectionEnabled=${prefs.getBoolean(\"enabled\", false)}",
                        )
                        result.success(true)
                    }
                }
                "addTime" -> {
'''
    native = replace_once(native, anchor, replacement, "قناة حفظ المدة")

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
print("Duration updates no longer toggle protection")
