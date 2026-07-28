from pathlib import Path

NATIVE = Path("native/MainActivityV2.kt")
FLUTTER = Path("lib/main.dart")
MARKER = "PARENT_PIN_UNINSTALL_PROTECTION_MARKER"
UI_MARKER = "PARENT_PIN_UNINSTALL_UI_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"تعذر دمج {label}: بداية المقطع غير موجودة")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"تعذر دمج {label}: نهاية المقطع غير موجودة")
    return text[:start_index] + replacement + text[end_index:]


native = NATIVE.read_text(encoding="utf-8")
flutter = FLUTTER.read_text(encoding="utf-8")
if MARKER in native and UI_MARKER in flutter:
    print("Parent PIN uninstall protection already merged")
    raise SystemExit(0)

policy_block = r'''// PARENT_PIN_UNINSTALL_PROTECTION_MARKER
private fun Context.ensureUninstallProtection(): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return false
    return try {
        manager.setUninstallBlocked(deviceAdminComponent(), packageName, true)
        appendGuardLog("UNINSTALL_PROTECTION_ENFORCED", "deviceOwner=true")
        true
    } catch (error: SecurityException) {
        appendGuardLog("UNINSTALL_PROTECTION_ENFORCE_FAILED", error = error)
        false
    }
}

private fun Context.configureDeviceOwnerPolicies(): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return false
    return try {
        val admin = deviceAdminComponent()
        manager.setLockTaskPackages(admin, arrayOf(packageName))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            manager.setLockTaskFeatures(admin, DevicePolicyManager.LOCK_TASK_FEATURE_NONE)
        }
        manager.setUninstallBlocked(admin, packageName, true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, true)
        }
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_APPLIED")
        true
    } catch (error: SecurityException) {
        appendGuardLog("DEVICE_OWNER_LOCK_POLICIES_FAILED", error = error)
        false
    }
}

private fun Context.releaseDeviceOwnerPolicies() {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    if (!manager.isDeviceOwnerApp(packageName)) return
    try {
        val admin = deviceAdminComponent()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setLockTaskPackages(admin, emptyArray<String>())
        // إيقاف حماية الوقت لا يسمح بحذف التطبيق. يبقى الحذف محمياً برمز الأب.
        manager.setUninstallBlocked(admin, packageName, true)
        appendGuardLog("RUNTIME_POLICIES_RELEASED_UNINSTALL_STILL_BLOCKED")
    } catch (error: SecurityException) {
        appendGuardLog("RUNTIME_POLICY_RELEASE_FAILED", error = error)
    }
}

private fun Activity.openSelfUninstallScreen() {
    startActivity(
        Intent(Intent.ACTION_DELETE, Uri.parse("package:$packageName")).addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP,
        ),
    )
    appendGuardLog("SYSTEM_UNINSTALL_SCREEN_OPENED")
}

private fun Activity.prepareParentAuthorizedUninstall(prefs: SharedPreferences): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    val admin = deviceAdminComponent()
    if (!manager.isDeviceOwnerApp(packageName)) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_REJECTED", "reason=device_owner_required")
        return false
    }

    return try {
        prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .remove("unlocked_date")
            .commit()
        syncBootProtectionState(false)
        stopService(Intent(this, MonitorService::class.java))

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setLockTaskPackages(admin, emptyArray<String>())
        manager.setUninstallBlocked(admin, packageName, false)
        appendGuardLog("UNINSTALL_AUTHORIZED_BY_PARENT_PIN", "deviceOwner=true")

        @Suppress("DEPRECATION")
        manager.clearDeviceOwnerApp(packageName)
        appendGuardLog("DEVICE_OWNER_CLEARED_FOR_UNINSTALL")
        true
    } catch (error: Exception) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_FAILED", error = error)
        false
    }
}

'''
native = replace_between(
    native,
    "private fun Context.configureDeviceOwnerPolicies(): Boolean {",
    "private fun readFailedAttempts",
    policy_block,
    "سياسات منع الحذف وإذن ولي الأمر",
)

native = replace_once(
    native,
    '        appendGuardLog("APP_ENGINE_READY", "activity=${javaClass.simpleName}")\n',
    '        appendGuardLog("APP_ENGINE_READY", "activity=${javaClass.simpleName}")\n'
    '        ensureUninstallProtection()\n',
    "إعادة فرض منع الحذف عند فتح التطبيق",
)
native = replace_once(
    native,
    '                    syncBootProtectionState(true)\n                    appendGuardLog("PROTECTION_ENABLED",',
    '                    syncBootProtectionState(true)\n'
    '                    ensureUninstallProtection()\n'
    '                    appendGuardLog("PROTECTION_ENABLED",',
    "إعادة فرض منع الحذف عند تشغيل الحماية",
)

uninstall_case = r'''                "authorizeUninstall" -> {
                    val pin = call.argument<String>("pin").orEmpty()
                    if (!verifyPin(prefs, pin)) {
                        recordFailedAttempt(this, prefs, "محاولة السماح بحذف التطبيق")
                        appendGuardLog("UNINSTALL_PIN_REJECTED")
                        result.error("WRONG_PIN", "رمز ولي الأمر غير صحيح", null)
                    } else {
                        val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                        if (!manager.isDeviceOwnerApp(packageName)) {
                            result.error(
                                "DEVICE_OWNER_REQUIRED",
                                "منع الحذف الكامل يحتاج تفعيل Device Owner أولاً",
                                null,
                            )
                        } else if (!prepareParentAuthorizedUninstall(prefs)) {
                            result.error(
                                "UNINSTALL_PREPARE_FAILED",
                                "تعذر إلغاء حماية الحذف بصورة آمنة",
                                null,
                            )
                        } else {
                            result.success(true)
                            Handler(Looper.getMainLooper()).postDelayed({
                                try {
                                    openSelfUninstallScreen()
                                } catch (error: Exception) {
                                    appendGuardLog("SYSTEM_UNINSTALL_SCREEN_FAILED", error = error)
                                }
                            }, 350L)
                        }
                    }
                }
'''
native = replace_once(
    native,
    '                "getDevicePolicyStatus" -> {\n',
    uninstall_case + '                "getDevicePolicyStatus" -> {\n',
    "قناة السماح بالحذف برمز الأب",
)
native = replace_once(
    native,
    '                    val deviceOwner = dpm.isDeviceOwnerApp(packageName)\n                    val uninstallBlocked = if (deviceOwner) {',
    '                    val deviceOwner = dpm.isDeviceOwnerApp(packageName)\n'
    '                    if (deviceOwner) ensureUninstallProtection()\n'
    '                    val uninstallBlocked = if (deviceOwner) {',
    "المعالجة الذاتية لحماية الحذف",
)
NATIVE.write_text(native, encoding="utf-8")

uninstall_ui = r'''  // PARENT_PIN_UNINSTALL_UI_MARKER
  Future<void> _authorizeUninstall() async {
    if (!_devicePolicy.deviceOwner) {
      await _showDeviceOwnerInstructions();
      return;
    }

    final pin = await _askPin(title: 'أدخل رمز الأب للسماح بالحذف');
    if (pin == null || !mounted) return;

    final confirmed = await showDialog<bool>(
          context: context,
          barrierDismissible: false,
          builder: (dialogContext) => AlertDialog(
            icon: const Icon(Icons.delete_forever_outlined),
            title: const Text('السماح بحذف التطبيق؟'),
            content: const Text(
              'سيتم إلغاء وضع Device Owner وفتح شاشة حذف Android. '
              'إذا ألغيت الحذف بعد ذلك فلن تعود الحماية الكاملة إلا بتفعيل Device Owner من الكمبيوتر مرة أخرى.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('رجوع'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: Theme.of(dialogContext).colorScheme.error,
                  foregroundColor: Theme.of(dialogContext).colorScheme.onError,
                ),
                onPressed: () => Navigator.pop(dialogContext, true),
                child: const Text('السماح بالحذف'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;

    await _runBusy(() async {
      try {
        await _channel.invokeMethod<void>('authorizeUninstall', {'pin': pin});
        _showMessage('تم قبول رمز الأب. أكمل الحذف من شاشة Android.');
      } on PlatformException catch (error) {
        await _refreshStatus(silent: true);
        _showMessage(error.message ?? 'تعذر السماح بحذف التطبيق.');
      }
    });
  }

'''
flutter = replace_once(
    flutter,
    "  Future<void> _configureDeviceOwnerPolicies() async {\n",
    uninstall_ui + "  Future<void> _configureDeviceOwnerPolicies() async {\n",
    "واجهة السماح بالحذف برمز الأب",
)

old_buttons = r'''                FilledButton.tonalIcon(
                  onPressed: _busy ? null : _configureDeviceOwnerPolicies,
                  icon: Icon(active ? Icons.security : Icons.info_outline),
                  label: Text(active ? 'تطبيق السياسات' : 'طريقة التفعيل'),
                ),
'''
new_buttons = r'''                FilledButton.tonalIcon(
                  onPressed: _busy ? null : _configureDeviceOwnerPolicies,
                  icon: Icon(active ? Icons.security : Icons.info_outline),
                  label: Text(active ? 'تطبيق السياسات' : 'طريقة التفعيل'),
                ),
                if (active)
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _authorizeUninstall,
                    icon: const Icon(Icons.delete_forever_outlined),
                    label: const Text('حذف التطبيق برمز الأب'),
                  ),
'''
flutter = replace_once(
    flutter,
    old_buttons,
    new_buttons,
    "زر حذف التطبيق المحمي",
)
flutter = replace_once(
    flutter,
    "                  ? 'التطبيق مضبوط كـ Device Owner ويمكن للنظام منع حذفه وتفعيل القفل المحكم.'\n",
    "                  ? 'لا يمكن حذف التطبيق من إعدادات Android. للسماح بالحذف يجب فتح التطبيق وإدخال رمز الأب.'\n",
    "شرح حماية الحذف",
)
FLUTTER.write_text(flutter, encoding="utf-8")

print("Parent PIN uninstall protection merged")
