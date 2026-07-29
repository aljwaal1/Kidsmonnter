from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MARKER = "MANDATORY_DEVICE_OWNER_SETUP_MARKER"
DEVICE_ADMIN_TOOL = Path("tools/merge_mandatory_device_admin_protection.py")


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
        "  bool get _runtimeSetupReady =>\n      (_status?.overlayAllowed == true) &&\n      _exactAlarmAllowed &&\n      _batteryOptimizationIgnored;\n",
        "  // MANDATORY_DEVICE_OWNER_SETUP_MARKER\n  bool get _runtimeSetupReady =>\n      (_status?.overlayAllowed == true) &&\n      _exactAlarmAllowed &&\n      _batteryOptimizationIgnored &&\n      _devicePolicy.uninstallProtectionActive;\n",
        "إضافة Device Owner إلى شروط الجاهزية",
    )

    anchor = "            const SizedBox(height: 18),\n            item(\n              ready: status.overlayAllowed,"
    replacement = """            const SizedBox(height: 18),
            item(
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
            const SizedBox(height: 10),
            item(
              ready: status.overlayAllowed,"""
    flutter = replace_once(flutter, anchor, replacement, "بطاقة منع الحذف الإلزامية")

if MARKER not in native:
    old = '''                    val missing = mutableListOf<String>()
                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")
'''
    new = '''                    // MANDATORY_DEVICE_OWNER_SETUP_MARKER
                    val missing = mutableListOf<String>()
                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                    val admin = ComponentName(this, KidsMonnterDeviceAdminReceiver::class.java)
                    val deviceOwnerReady = dpm.isDeviceOwnerApp(packageName) &&
                        dpm.isAdminActive(admin) &&
                        dpm.isUninstallBlocked(admin, packageName)
                    if (!deviceOwnerReady) missing.add("device_owner_uninstall_block")
                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")
'''
    native = replace_once(native, old, new, "التحقق الأصلي من منع الحذف")

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
print("Mandatory Device Owner setup merged")
namespace = {"__name__": "__main__", "__file__": str(DEVICE_ADMIN_TOOL)}
exec(compile(DEVICE_ADMIN_TOOL.read_text(encoding="utf-8"), str(DEVICE_ADMIN_TOOL), "exec"), namespace)
