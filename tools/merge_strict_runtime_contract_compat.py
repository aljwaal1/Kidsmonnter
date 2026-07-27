from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
marker = "STRICT_RUNTIME_CONTRACT_COMPAT_MARKER"
if marker in source:
    print("Strict runtime compatibility already merged")
    raise SystemExit(0)

old_status = '''                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) {
                        requestMonitorServiceStartIfAllowed(prefs).also {
                            appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                        }
                    }
'''
new_status = '''                // STRICT_RUNTIME_CONTRACT_COMPAT_MARKER
                "getStatus" -> {
                    if (shouldRecoverProtectionService(prefs)) requestMonitorServiceStartIfAllowed(prefs).also {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                    }
'''
if old_status not in source:
    raise SystemExit("تعذر استعادة عقد getStatus القديم")
source = source.replace(old_status, new_status, 1)

old_boot_call = '''                    context.requestMonitorServiceStartIfAllowed(
                        prefs,
                        force = action != MONITOR_WATCHDOG_ACTION,
                    )
'''
new_boot_call = '''                    context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)
'''
if old_boot_call not in source:
    raise SystemExit("تعذر استعادة عقد watchdog القديم")
source = source.replace(old_boot_call, new_boot_call, 1)

path.write_text(source, encoding="utf-8")
print("Strict runtime compatibility merged")
