from pathlib import Path


path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")

helper_marker = "private fun Context.releaseDeviceOwnerPolicies()"
if helper_marker not in source:
    anchor = "private fun readFailedAttempts"
    if anchor not in source:
        raise RuntimeError("Could not locate policy helper insertion anchor")

    helper = '''private fun Context.releaseDeviceOwnerPolicies() {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return
    try {
        val admin = deviceAdminComponent()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setUninstallBlocked(admin, packageName, false)
        manager.setLockTaskPackages(admin, emptyArray<String>())
    } catch (_: SecurityException) {
        // The service is still stopped even if a vendor rejects one policy reset.
    }
}

'''
    source = source.replace(anchor, helper + anchor, 1)


def insert_release_call(start_marker: str, end_marker: str, label: str) -> None:
    global source
    start = source.find(start_marker)
    end = source.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise RuntimeError(f"Could not locate {label} block")

    block = source[start:end]
    if "releaseDeviceOwnerPolicies()" in block:
        return

    stop_line = "stopService(Intent(this, MonitorService::class.java))"
    if stop_line not in block:
        raise RuntimeError(f"Could not locate service stop in {label} block")

    block = block.replace(
        stop_line,
        "releaseDeviceOwnerPolicies()\n" + " " * (block.index(stop_line) - block.rfind("\n", 0, block.index(stop_line)) - 1) + stop_line,
        1,
    )
    source = source[:start] + block + source[end:]


insert_release_call(
    '                "stopProtection" -> {',
    '                "addTime" -> {',
    "main stopProtection",
)
insert_release_call(
    "    private fun disableProtectionWithPin() {",
    "    private fun unlockWithPin(addTime: Boolean) {",
    "lock emergency stop",
)

path.write_text(source, encoding="utf-8")
print("Device-owner restrictions are safely released when protection stops")
