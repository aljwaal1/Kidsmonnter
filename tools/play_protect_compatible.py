from pathlib import Path
import re
import runpy

# Remove the Accessibility service from the sideloaded consumer APK.
# Strong uninstall blocking remains available when the app is provisioned
# as Device Owner and uses DevicePolicyManager.setUninstallBlocked().

GENERATED_MANIFEST = Path("android/app/src/main/AndroidManifest.xml")
SOURCE_MANIFEST = Path("native/AndroidManifest.xml")
GENERATED_KOTLIN = Path(
    "android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt"
)
SOURCE_KOTLIN = Path("native/MainActivityV2.kt")
FLUTTER = Path("lib/main.dart")


def remove_accessibility_service(path: Path, required: bool) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"\n\s*<service\s+android:name=\"\.UninstallGuardAccessibilityService\".*?</service>\s*\n",
        "\n",
        text,
        count=1,
        flags=re.S,
    )
    if required and count != 1:
        raise SystemExit(
            f"Expected one Accessibility service declaration in {path}, found {count}"
        )
    if count:
        path.write_text(updated, encoding="utf-8")


def remove_mandatory_accessibility_check(path: Path, required: bool) -> None:
    text = path.read_text(encoding="utf-8")
    old = '                    if (!isUninstallGuardAccessibilityEnabled()) missing.add("uninstall_guard")\n'
    if required and old not in text:
        raise SystemExit(f"Mandatory Accessibility check was not found in {path}")
    if old in text:
        path.write_text(text.replace(old, "", 1), encoding="utf-8")


remove_accessibility_service(GENERATED_MANIFEST, required=True)
remove_accessibility_service(SOURCE_MANIFEST, required=False)
remove_mandatory_accessibility_check(GENERATED_KOTLIN, required=True)
remove_mandatory_accessibility_check(SOURCE_KOTLIN, required=False)

flutter = FLUTTER.read_text(encoding="utf-8")
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
flutter = flutter.replace("title: 'منع حذف التطبيق',", "title: 'مسؤول الجهاز',", 1)
flutter = flutter.replace(
    "? 'مسؤول الجهاز مفعّل. تبقى خدمة الحماية فوق محاولات الوصول إلى الحذف أثناء عمل الحماية.'",
    "? 'مسؤول الجهاز مفعّل. في وضع Device Owner يمكن تطبيق منع حذف نظامي، وفي التثبيت العادي يدعم استمرار القفل.'",
    1,
)
FLUTTER.write_text(flutter, encoding="utf-8")

print("Play Protect compatible consumer build patch applied")

# The official unified APK now requires the strict Device Owner path.
runpy.run_path("tools/strict_parental_mode.py", run_name="__main__")
