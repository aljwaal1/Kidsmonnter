from pathlib import Path

FLUTTER = Path("lib/main.dart")
MARKER = "DEFAULT_UNINSTALL_PROTECTION_UI_MARKER"
DAILY_REPORTS_TOOL = Path("tools/merge_daily_failed_attempt_reports.py")
MANDATORY_SETUP_TOOL = Path("tools/merge_mandatory_runtime_setup.py")


def run_merge_tool(path: Path) -> None:
    namespace = {"__name__": "__main__", "__file__": str(path)}
    try:
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    except SystemExit as error:
        if error.code not in (None, 0):
            raise


def run_followup_merges() -> None:
    run_merge_tool(DAILY_REPORTS_TOOL)
    run_merge_tool(MANDATORY_SETUP_TOOL)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


flutter = FLUTTER.read_text(encoding="utf-8")
if MARKER in flutter:
    print("Default uninstall protection UI already merged")
    run_followup_merges()
    raise SystemExit(0)

old_entry = '''            _buildUninstallProtectionCard(status),
            const SizedBox(height: 10),
'''
new_entry = '''            // DEFAULT_UNINSTALL_PROTECTION_UI_MARKER
            const Divider(height: 24),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                _devicePolicy.uninstallProtectionActive
                    ? Icons.verified_user
                    : Icons.info_outline,
                color: _devicePolicy.uninstallProtectionActive
                    ? Colors.green
                    : Colors.orange,
              ),
              title: Text(
                _devicePolicy.uninstallProtectionActive
                    ? 'منع حذف التطبيق يعمل تلقائيًا'
                    : 'منع الحذف يحتاج إعداد الجهاز مرة واحدة',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              subtitle: Text(
                _devicePolicy.uninstallProtectionActive
                    ? 'لا يوجد زر تشغيل. لا يمكن حذف التطبيق إلا من هنا وبعد رمز الأب.'
                    : 'اضغط لمعرفة خطوة Device Owner؛ بعدها يصبح منع الحذف افتراضيًا دائمًا.',
              ),
              trailing: _devicePolicy.uninstallProtectionActive
                  ? TextButton.icon(
                      onPressed: _busy ? null : _authorizeUninstall,
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('حذف'),
                    )
                  : const Icon(Icons.chevron_left),
              onTap: _busy || _devicePolicy.uninstallProtectionActive
                  ? null
                  : _showDeviceOwnerInstructions,
            ),
            const Divider(height: 24),
'''
flutter = replace_once(
    flutter,
    old_entry,
    new_entry,
    "الحالة التلقائية المبسطة لمنع الحذف",
)

method_start = flutter.find("  Widget _buildUninstallProtectionCard(GuardStatus status) {")
if method_start < 0:
    raise SystemExit("تعذر إزالة بطاقة منع الحذف القديمة: بداية الدالة غير موجودة")
class_end = flutter.rfind("\n}")
if class_end <= method_start:
    raise SystemExit("تعذر إزالة بطاقة منع الحذف القديمة: نهاية الصنف غير موجودة")
flutter = flutter[:method_start] + flutter[class_end:]

FLUTTER.write_text(flutter, encoding="utf-8")
print("Default uninstall protection UI merged")
run_followup_merges()
