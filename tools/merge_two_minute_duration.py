from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MARKER = "TWO_MINUTE_DURATION_MARKER"

flutter = FLUTTER.read_text(encoding="utf-8")
native = NATIVE.read_text(encoding="utf-8")

if MARKER not in flutter:
    flutter = flutter.replace(
        "static const List<int> _durationOptions = <int>[10, 30, 60, 90, 120, 180];",
        "// TWO_MINUTE_DURATION_MARKER\n  static const List<int> _durationOptions = <int>[2, 10, 30, 60, 90, 120, 180];",
        1,
    )
    flutter = flutter.replace("_status?.dailyMinutes ?? 60", "_status?.dailyMinutes ?? 10")
    flutter = flutter.replace("(_status?.dailyMinutes ?? 60) * 60", "(_status?.dailyMinutes ?? 10) * 60")
    flutter = flutter.replace("      case 10:\n        return '10 دقائق';", "      case 2:\n        return 'دقيقتان';\n      case 10:\n        return '10 دقائق';", 1)

native = native.replace('(call.argument<Int>("minutes") ?: 60)', '(call.argument<Int>("minutes") ?: 10)')
native = native.replace('prefs.getInt("daily_minutes", 60)', 'prefs.getInt("daily_minutes", 10)')
native = native.replace('getInt("daily_minutes", 60)', 'getInt("daily_minutes", 10)')

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
print("Two-minute duration and 10-minute default merged")
