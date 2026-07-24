from pathlib import Path

native_path = Path('native/MainActivityV2.kt')
source = native_path.read_text(encoding='utf-8')

method_marker = '                "restartProtectionService" -> {'
if method_marker not in source:
    anchor = '                "stopProtection" -> {'
    if anchor not in source:
        raise SystemExit('Could not locate stopProtection method anchor')

    method = '''                "restartProtectionService" -> {
                    if (!prefs.getBoolean("enabled", false)) {
                        result.error("PROTECTION_DISABLED", "الحماية غير مفعلة", null)
                    } else {
                        startMonitorServiceSafely()
                        result.success(true)
                    }
                }
'''
    source = source.replace(anchor, method + anchor, 1)

native_path.write_text(source, encoding='utf-8')
print('Dedicated service restart channel is present.')
