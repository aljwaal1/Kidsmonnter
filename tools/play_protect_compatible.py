from pathlib import Path
import re

# This patch intentionally removes the Accessibility service from the
# sideloaded consumer APK. Strong uninstall blocking remains available when
# the app is provisioned as Device Owner, using DevicePolicyManager.

manifest_path = Path("android/app/src/main/AndroidManifest.xml")
kotlin_path = Path("android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt")
flutter_path = Path("lib/main.dart")

manifest = manifest_path.read_text(encoding="utf-8")
manifest, count = re.subn(
    r"\n\s*<service\s+android:name=\"\.UninstallGuardAccessibilityService\".*?</service>\s*\n",
    "\n",
    manifest,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit(f"Expected one Accessibility service declaration, found {count}")
manifest_path.write_text(manifest, encoding="utf-8")

kotlin = kotlin_path.read_text(encoding="utf-8")
old = '                    if (!isUninstallGuardAccessibilityEnabled()) missing.add("uninstall_guard")\n'
if old not in kotlin:
    raise SystemExit("Mandatory Accessibility runtime check was not found")
kotlin = kotlin.replace(old, "", 1)
kotlin_path.write_text(kotlin, encoding="utf-8")

flutter = flutter_path.read_text(encoding="utf-8")
old_ready = "      _batteryOptimizationIgnored &&\n      _uninstallGuardEnabled &&\n      _devicePolicy.adminActive;"
new_ready = "      _batteryOptimizationIgnored &&\n      _devicePolicy.adminActive;"
if old_ready not in flutter:
    raise SystemExit("Flutter mandatory Accessibility condition was not found")
flutter = flutter.replace(old_ready, new_ready, 1)

old_card = """            item(
              ready: _uninstallGuardEnabled,
              title: 'قفل الحذف برمز الأب',
              subtitle: _uninstallGuardEnabled
                  ? 'مفعّل: تتم مقاطعة شاشة حذف التطبيق ويُطلب رمز الأب.'
                  : 'إجباري: فعّل خدمة حارس وقت الأطفال ضمن إمكانية الوصول.',
              action: () => _openRequiredSetting('openAccessibilitySettings'),
              button: 'تفعيل حارس الحذف',
            ),
            const SizedBox(height: 10),
"""
new_card = """            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      _devicePolicy.uninstallProtectionActive
                          ? Icons.verified_user
                          : Icons.info_outline,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _devicePolicy.uninstallProtectionActive
                            ? 'منع الحذف النظامي مفعّل عبر Device Owner، ولا يُفك إلا برمز ولي الأمر.'
                            : 'التثبيت العادي لا يستخدم خدمة إمكانية الوصول. منع الحذف غير القابل للتجاوز يتطلب تجهيز الجهاز كـ Device Owner؛ أما القفل والعداد فيعملان بعد إكمال الصلاحيات الظاهرة.',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
"""
if old_card not in flutter:
    raise SystemExit("Flutter Accessibility setup card was not found")
flutter = flutter.replace(old_card, new_card, 1)
flutter = flutter.replace(
    "title: 'منع حذف التطبيق',",
    "title: 'مسؤول الجهاز',",
    1,
)
flutter = flutter.replace(
    "? 'مسؤول الجهاز مفعّل. تبقى خدمة الحماية فوق محاولات الوصول إلى الحذف أثناء عمل الحماية.'",
    "? 'مسؤول الجهاز مفعّل. في وضع Device Owner يمكن تطبيق منع حذف نظامي، وفي التثبيت العادي يدعم استمرار القفل.'",
    1,
)
flutter_path.write_text(flutter, encoding="utf-8")

print("Play Protect compatible consumer build patch applied")
