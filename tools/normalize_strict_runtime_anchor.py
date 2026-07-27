from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
expected = '''                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) {
'''
if expected in source:
    print("Strict runtime getStatus anchor already normalized")
    raise SystemExit(0)

old = '''                "getStatus" -> {
                    // RUNTIME_DIAGNOSTICS_CONTRACT_COMPAT_MARKER
                    if (shouldRecoverProtectionService(prefs)) requestMonitorServiceStartIfAllowed(prefs).also {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                    }
'''
new = '''                "getStatus" -> {
                    // RUNTIME_DIAGNOSTICS_CONTRACT_COMPAT_MARKER
                    if (shouldRecoverProtectionService(prefs)) {
                        requestMonitorServiceStartIfAllowed(prefs).also {
                            appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                        }
                    }
'''
if old not in source:
    raise SystemExit("تعذر توحيد كتلة getStatus للاستمرارية الصارمة")
path.write_text(source.replace(old, new, 1), encoding="utf-8")
print("Strict runtime getStatus anchor normalized")
