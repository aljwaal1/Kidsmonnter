from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MARKER = "MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER"
UNINSTALL_GUARD_TOOL = Path("tools/merge_parent_pin_uninstall_guard.py")
UNINSTALL_GUARD_ORDER_TOOL = Path("tools/fix_uninstall_guard_class_order.py")
DURATION_WITHOUT_TOGGLE_TOOL = Path("tools/merge_duration_without_toggle.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


flutter = FLUTTER.read_text(encoding="utf-8")
native = NATIVE.read_text(encoding="utf-8")

if MARKER not in flutter:
    flutter = replace_once(
        flutter,
        "      _batteryOptimizationIgnored &&\n      _devicePolicy.uninstallProtectionActive;",
        "      _batteryOptimizationIgnored &&\n      _devicePolicy.adminActive; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER",
        "اعتماد مسؤول الجهاز بدل Device Owner",
    )

    flutter = replace_once(
        flutter,
        "  Future<void> _openRequiredSetting(String method) async {",
        """  Future<void> _activateDeviceAdministrator() async {
    try {
      await _channel.invokeMethod<void>('activateDeviceAdministrator');
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر فتح شاشة تفعيل مسؤول الجهاز.');
    }
  }

  Future<void> _openRequiredSetting(String method) async {""",
        "زر تفعيل مسؤول الجهاز",
    )

    old_card = """            item(
              ready: _devicePolicy.uninstallProtectionActive,
              title: 'منع حذف التطبيق',
              subtitle: _devicePolicy.uninstallProtectionActive
                  ? 'تم تفعيل Device Owner ومنع الحذف من إعدادات Android.'
                  : 'هذه أهم خطوة. بدونها يمكن حذف التطبيق وإلغاء الحماية بالكامل.',
              action: _showDeviceOwnerInstructions,
              button: 'إعداد منع الحذف',
            ),
            if (!_devicePolicy.uninstallProtectionActive) ...[
              const SizedBox(height: 8),
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(14),
                  child: Text(
                    'لا يمكن تفعيل Device Owner من داخل التطبيق بعد إعداد الهاتف. يلزم جهاز جديد أو إعادة ضبط المصنع، ثم تثبيت التطبيق وتنفيذ أمر ADB قبل إضافة حساب Google أو إنشاء مستخدمين.',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
"""
    new_card = """            item(
              ready: _devicePolicy.adminActive,
              title: 'منع حذف التطبيق',
              subtitle: _devicePolicy.adminActive
                  ? 'مسؤول الجهاز مفعّل. تبقى خدمة الحماية فوق محاولات الوصول إلى الحذف أثناء عمل الحماية.'
                  : 'فعّل مسؤول الجهاز من شاشة Android. لا يحتاج كمبيوترًا أو إعادة ضبط المصنع.',
              action: _activateDeviceAdministrator,
              button: 'تفعيل مسؤول الجهاز',
            ),
            if (!_devicePolicy.adminActive) ...[
              const SizedBox(height: 8),
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(14),
                  child: Text(
                    'هذه الخطوة إجبارية: اضغط تفعيل مسؤول الجهاز ثم اختر «تنشيط». لن تبدأ الحماية قبل نجاحها.',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
"""
    flutter = replace_once(flutter, old_card, new_card, "بطاقة مسؤول الجهاز الإلزامية")

if MARKER not in native:
    old_check = """                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)
                    val deviceOwnerReady = dpm.isDeviceOwnerApp(packageName) &&
                        dpm.isAdminActive(admin) &&
                        dpm.isUninstallBlocked(admin, packageName)
                    if (!deviceOwnerReady) missing.add("device_owner_uninstall_block")
"""
    new_check = """                    // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER
                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)
                    if (!dpm.isAdminActive(admin)) missing.add("device_admin")
"""
    native = replace_once(native, old_check, new_check, "التحقق الأصلي من مسؤول الجهاز")

    native = replace_once(
        native,
        "                // MANDATORY_RUNTIME_SETUP_MARKER\n                \"startProtection\" -> {",
        """                "activateDeviceAdministrator" -> {
                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)
                    if (dpm.isAdminActive(admin)) {
                        result.success(true)
                    } else {
                        startActivity(
                            Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
                                putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin)
                                putExtra(
                                    DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                                    "يلزم تفعيل مسؤول الجهاز حتى لا يمكن إيقاف حماية وقت الهاتف بسهولة.",
                                )
                            },
                        )
                        result.success(true)
                    }
                }
                // MANDATORY_RUNTIME_SETUP_MARKER
                "startProtection" -> {""",
        "قناة تفعيل مسؤول الجهاز",
    )

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
print("Mandatory device-admin protection merged")
for tool in (
    UNINSTALL_GUARD_TOOL,
    UNINSTALL_GUARD_ORDER_TOOL,
    DURATION_WITHOUT_TOGGLE_TOOL,
):
    namespace = {"__name__": "__main__", "__file__": str(tool)}
    exec(compile(tool.read_text(encoding="utf-8"), str(tool), "exec"), namespace)
