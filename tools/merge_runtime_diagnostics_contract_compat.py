from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
marker = "RUNTIME_DIAGNOSTICS_CONTRACT_COMPAT_MARKER"

if marker in source:
    print("توافق عقود سجل التشخيص مدمج مسبقاً")
    raise SystemExit(0)

old_status = '''                    if (shouldRecoverProtectionService(prefs)) {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)}")
                        requestMonitorServiceStartIfAllowed(prefs)
                    }
'''
new_status = '''                    // RUNTIME_DIAGNOSTICS_CONTRACT_COMPAT_MARKER
                    if (shouldRecoverProtectionService(prefs)) requestMonitorServiceStartIfAllowed(prefs).also {
                        appendGuardLog("STATUS_SELF_HEAL", "heartbeat=${prefs.getLong(HEARTBEAT_KEY, 0L)} requested=$it")
                    }
'''
if old_status not in source:
    raise SystemExit("تعذر الحفاظ على عقد الاستعادة الذاتية: المقطع غير موجود")
source = source.replace(old_status, new_status, 1)

old_start = '''    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        appendGuardLog("SERVICE_START_COMMAND", "action=${intent?.action.orEmpty()} flags=$flags startId=$startId")
        return try {
            resetClockAnchor()
            enforceLockIfNeeded()
            START_STICKY
        } catch (error: Exception) {
            appendGuardLog("SERVICE_START_COMMAND_ERROR", error = error)
            START_STICKY
        }
    }
'''
new_start = '''    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        appendGuardLog("SERVICE_START_COMMAND", "action=${intent?.action.orEmpty()} flags=$flags startId=$startId")
        try {
            resetClockAnchor()
            enforceLockIfNeeded()
        } catch (error: Exception) {
            appendGuardLog("SERVICE_START_COMMAND_ERROR", error = error)
        }
        return START_STICKY
    }
'''
if old_start not in source:
    raise SystemExit("تعذر الحفاظ على عقد START_STICKY: المقطع غير موجود")
source = source.replace(old_start, new_start, 1)

path.write_text(source, encoding="utf-8")
print("تم الحفاظ على عقود الاستعادة وSTART_STICKY مع سجل التشخيص")
