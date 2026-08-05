from pathlib import Path
import re

kotlin_path = Path('android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt')
flutter_path = Path('lib/main.dart')

kotlin = kotlin_path.read_text(encoding='utf-8')

# Strict mode is the official mode: Device Owner is mandatory. Overlay is only a fallback.
old_requirements = '''                    if (!dpm.isAdminActive(admin)) missing.add("device_admin")
                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")
                    if (!isIgnoringBatteryOptimizations()) missing.add("battery")
                    if (!canUseExactWatchdog()) missing.add("exact_alarm")'''
new_requirements = '''                    if (!dpm.isDeviceOwnerApp(packageName)) missing.add("device_owner")
                    if (!dpm.isAdminActive(admin)) missing.add("device_admin")
                    if (!isIgnoringBatteryOptimizations()) missing.add("battery")
                    if (!canUseExactWatchdog()) missing.add("exact_alarm")'''
if old_requirements not in kotlin:
    raise SystemExit('Strict-mode runtime requirements block was not found')
kotlin = kotlin.replace(old_requirements, new_requirements, 1)

old_enable = '''                        .putBoolean("enabled", true)
                        .putString("date", today())'''
new_enable = '''                        .putBoolean("enabled", true)
                        .putBoolean("strict_mode", true)
                        .putString("date", today())'''
if old_enable not in kotlin:
    raise SystemExit('Protection enable preferences block was not found')
kotlin = kotlin.replace(old_enable, new_enable, 1)

# Device-owner preparation should not hide the status bar until the lock is active.
status_bar_block = '''        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, true)
        }
'''
if status_bar_block not in kotlin:
    raise SystemExit('Device-owner status-bar policy block was not found')
kotlin = kotlin.replace(status_bar_block, '', 1)

helper_anchor = '''private fun Context.releaseDeviceOwnerPolicies() {'''
strict_helper = '''private fun Context.setStrictLockUi(active: Boolean) {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return
    try {
        val admin = deviceAdminComponent()
        manager.setLockTaskPackages(admin, if (active) arrayOf(packageName) else emptyArray<String>())
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            manager.setLockTaskFeatures(admin, DevicePolicyManager.LOCK_TASK_FEATURE_NONE)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, active)
        }
        manager.setUninstallBlocked(admin, packageName, true)
        appendGuardLog("STRICT_LOCK_UI_CHANGED", "active=$active")
    } catch (error: SecurityException) {
        appendGuardLog("STRICT_LOCK_UI_CHANGE_FAILED", "active=$active", error)
    }
}

'''
if helper_anchor not in kotlin:
    raise SystemExit('Release-policy helper anchor was not found')
kotlin = kotlin.replace(helper_anchor, strict_helper + helper_anchor, 1)

old_lock_create = '''        configureDeviceOwnerPolicies()
        window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)'''
new_lock_create = '''        configureDeviceOwnerPolicies()
        setStrictLockUi(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)'''
if old_lock_create not in kotlin:
    raise SystemExit('LockActivity onCreate anchor was not found')
kotlin = kotlin.replace(old_lock_create, new_lock_create, 1)

old_exit = '''    private fun exitLock() {
        authorizedExit = true
        handler.removeCallbacksAndMessages(null)
        try { stopLockTask() } catch (_: Exception) {}
        finishAndRemoveTask()'''
new_exit = '''    private fun exitLock() {
        authorizedExit = true
        handler.removeCallbacksAndMessages(null)
        try { stopLockTask() } catch (_: Exception) {}
        setStrictLockUi(false)
        finishAndRemoveTask()'''
if old_exit not in kotlin:
    raise SystemExit('LockActivity exit block was not found')
kotlin = kotlin.replace(old_exit, new_exit, 1)

# Return explicit strict-mode diagnostics to Flutter.
old_policy_map = '''                        "deviceOwner" to deviceOwner,
                        "adminActive" to dpm.isAdminActive(admin),
                        "lockTaskPermitted" to dpm.isLockTaskPermitted(packageName),
                        "uninstallBlocked" to uninstallBlocked'''
new_policy_map = '''                        "deviceOwner" to deviceOwner,
                        "adminActive" to dpm.isAdminActive(admin),
                        "lockTaskPermitted" to dpm.isLockTaskPermitted(packageName),
                        "uninstallBlocked" to uninstallBlocked,
                        "strictReady" to (deviceOwner && dpm.isAdminActive(admin) &&
                            dpm.isLockTaskPermitted(packageName) && uninstallBlocked),
                        "strictMode" to prefs.getBoolean("strict_mode", true)'''
if old_policy_map not in kotlin:
    raise SystemExit('Device policy status map was not found')
kotlin = kotlin.replace(old_policy_map, new_policy_map, 1)

# Configuration now validates the result rather than returning success unconditionally.
old_configure = '''                "configureDeviceOwner" -> {
                    configureDeviceOwnerPolicies()
                    result.success(true)
                }'''
new_configure = '''                "configureDeviceOwner" -> {
                    val configured = configureDeviceOwnerPolicies()
                    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val ready = configured && manager.isDeviceOwnerApp(packageName) &&
                        manager.isLockTaskPermitted(packageName) && ensureUninstallProtection()
                    if (ready) result.success(true) else result.error(
                        "DEVICE_OWNER_REQUIRED",
                        "الوضع الأبوي الصارم يتطلب تجهيز هذا التطبيق كـ Device Owner.",
                        null,
                    )
                }'''
if old_configure not in kotlin:
    raise SystemExit('configureDeviceOwner channel handler was not found')
kotlin = kotlin.replace(old_configure, new_configure, 1)

kotlin += '\n// STRICT_PARENTAL_DEVICE_OWNER_V1\n'
kotlin_path.write_text(kotlin, encoding='utf-8')

flutter = flutter_path.read_text(encoding='utf-8')

# DevicePolicyStatus gains an explicit strictReady field.
flutter = flutter.replace(
    '''    required this.uninstallBlocked,\n  });''',
    '''    required this.uninstallBlocked,\n    required this.strictReady,\n  });''',
    1,
)
flutter = flutter.replace(
    '''  final bool uninstallBlocked;''',
    '''  final bool uninstallBlocked;\n  final bool strictReady;''',
    1,
)
flutter = flutter.replace(
    '''      uninstallBlocked: map?['uninstallBlocked'] == true,\n    );''',
    '''      uninstallBlocked: map?['uninstallBlocked'] == true,\n      strictReady: map?['strictReady'] == true,\n    );''',
    1,
)
flutter = flutter.replace(
    '''    uninstallBlocked: false,\n  );''',
    '''    uninstallBlocked: false,\n    strictReady: false,\n  );''',
    1,
)

# The strict app no longer treats Overlay as a prerequisite; Device Owner is mandatory.
pattern = re.compile(
    r'''  bool get _runtimeSetupReady =>\n(?:.*\n){1,8}?      _devicePolicy\.adminActive; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'''
)
replacement = '''  bool get _runtimeSetupReady =>
      _devicePolicy.strictReady &&
      _exactAlarmAllowed &&
      _batteryOptimizationIgnored; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'''
flutter, count = pattern.subn(replacement, flutter, count=1)
if count != 1:
    raise SystemExit(f'Flutter runtime readiness block replacement count={count}')

# Make the setup screen truthful and strict.
flutter = flutter.replace(
    "'لا يمكن استخدام التطبيق قبل إكمال صلاحيات الحماية'",
    "'يلزم تجهيز الجهاز للوضع الأبوي الصارم'",
    1,
)
flutter = flutter.replace(
    "'هذه الخطوات ضرورية حتى يستمر احتساب الوقت ولا يوقف نظام الهاتف خدمة الحماية.'",
    "'لن تبدأ الحماية قبل تحقق Device Owner وLock Task ومنع الحذف النظامي. بعد ذلك يقفل الهاتف عند انتهاء الوقت ولا يفتح إلا برمز ولي الأمر.'",
    1,
)
flutter = flutter.replace(
    "ready: _devicePolicy.adminActive,",
    "ready: _devicePolicy.strictReady,",
    1,
)
flutter = flutter.replace(
    "title: 'مسؤول الجهاز',",
    "title: 'الإدارة الأبوية الصارمة',",
    1,
)
flutter = flutter.replace(
    "title: 'منع حذف التطبيق',",
    "title: 'الإدارة الأبوية الصارمة',",
    1,
)

flutter += '\n// STRICT_PARENTAL_DEVICE_OWNER_UI_V1\n'
flutter_path.write_text(flutter, encoding='utf-8')

print('Strict parental Device Owner mode applied')
