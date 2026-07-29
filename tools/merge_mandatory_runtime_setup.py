from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MARKER = "MANDATORY_RUNTIME_SETUP_MARKER"
TWO_MINUTE_TOOL = Path("tools/merge_two_minute_duration.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


flutter = FLUTTER.read_text(encoding="utf-8")
native = NATIVE.read_text(encoding="utf-8")

if MARKER not in flutter:
    old = '''  Future<void> _setProtection(bool enabled) async {
'''
    new = '''  // MANDATORY_RUNTIME_SETUP_MARKER
  bool get _runtimeSetupReady =>
      (_status?.overlayAllowed == true) &&
      _exactAlarmAllowed &&
      _batteryOptimizationIgnored;

  Future<void> _openRequiredSetting(String method) async {
    try {
      await _channel.invokeMethod<void>(method);
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر فتح إعداد النظام.');
    }
  }

  Widget _buildMandatorySetupScreen() {
    final status = _status!;
    Widget item({
      required bool ready,
      required String title,
      required String subtitle,
      required VoidCallback action,
      required String button,
    }) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                ready ? Icons.check_circle : Icons.error_outline,
                color: ready ? Colors.green : Colors.orange,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text(subtitle),
                    if (!ready) ...[
                      const SizedBox(height: 10),
                      FilledButton.tonal(
                        onPressed: action,
                        child: Text(button),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('إعداد الحماية الإجباري')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Icon(Icons.admin_panel_settings_outlined, size: 64),
            const SizedBox(height: 12),
            const Text(
              'لا يمكن استخدام التطبيق قبل إكمال صلاحيات الحماية',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'هذه الخطوات ضرورية حتى يستمر احتساب الوقت ولا يوقف نظام الهاتف خدمة الحماية.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            item(
              ready: status.overlayAllowed,
              title: 'الظهور فوق التطبيقات',
              subtitle: 'ضروري لإظهار شاشة القفل عند انتهاء الوقت.',
              action: () => _openRequiredSetting('openOverlaySettings'),
              button: 'تفعيل الصلاحية',
            ),
            const SizedBox(height: 10),
            item(
              ready: _batteryOptimizationIgnored,
              title: 'استثناء التطبيق من تحسين البطارية',
              subtitle: 'يمنع Android من تجميد خدمة احتساب الوقت في الخلفية.',
              action: () =>
                  _openRequiredSetting('openBatteryOptimizationSettings'),
              button: 'استثناء البطارية',
            ),
            const SizedBox(height: 10),
            item(
              ready: _exactAlarmAllowed,
              title: 'المنبهات والتذكيرات الدقيقة',
              subtitle: 'تسمح للمراقب بإعادة خدمة الحماية في الوقت المناسب.',
              action: () => _openRequiredSetting('openExactAlarmSettings'),
              button: 'تفعيل المنبه الدقيق',
            ),
            const SizedBox(height: 10),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.info_outline),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'في أجهزة HONOR افتح الإعدادات > البطارية > تشغيل التطبيقات، ثم عطّل الإدارة التلقائية للتطبيق وفعّل التشغيل التلقائي والتشغيل في الخلفية. لا يوفّر Android طريقة موحدة للتحقق من هذه الخطوة آليًا.',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _busy ? null : () => _refreshStatus(),
              icon: const Icon(Icons.refresh),
              label: const Text('تحقق من الصلاحيات'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _setProtection(bool enabled) async {
'''
    flutter = replace_once(flutter, old, new, "شاشة الإعداد الإجباري")

    old = '''        if (enabled) {
          if (!await _ensurePin()) return;
'''
    new = '''        if (enabled) {
          await _refreshStatus(silent: true);
          if (!_runtimeSetupReady) {
            _showMessage('أكمل صلاحيات الحماية الإلزامية أولًا.');
            return;
          }
          if (!await _ensurePin()) return;
'''
    flutter = replace_once(flutter, old, new, "منع التفعيل قبل الصلاحيات")

    old = '''    final scheme = Theme.of(context).colorScheme;
'''
    new = '''    if (!_runtimeSetupReady) {
      return _buildMandatorySetupScreen();
    }

    final scheme = Theme.of(context).colorScheme;
'''
    flutter = replace_once(flutter, old, new, "حجب الواجهة الرئيسية")

if MARKER not in native:
    old = '''                "startProtection" -> {
                    val minutes = (call.argument<Int>("minutes") ?: 60).coerceIn(1, 1440)
'''
    new = '''                // MANDATORY_RUNTIME_SETUP_MARKER
                "startProtection" -> {
                    val missing = mutableListOf<String>()
                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")
                    if (!isIgnoringBatteryOptimizations()) missing.add("battery")
                    if (!canUseExactWatchdog()) missing.add("exact_alarm")
                    if (missing.isNotEmpty()) {
                        appendGuardLog("PROTECTION_START_BLOCKED", "missing=${missing.joinToString(",")}")
                        result.error(
                            "MISSING_RUNTIME_REQUIREMENTS",
                            "يجب تفعيل صلاحيات الحماية الإلزامية أولًا: ${missing.joinToString(", ")}",
                            missing,
                        )
                    } else {
                    val minutes = (call.argument<Int>("minutes") ?: 60).coerceIn(1, 1440)
'''
    native = replace_once(native, old, new, "التحقق الأصلي من الصلاحيات")

    old = '''                    result.success(true)
                }
                "restartProtectionService" -> {
'''
    new = '''                    result.success(true)
                    }
                }
                "restartProtectionService" -> {
'''
    native = replace_once(native, old, new, "إغلاق شرط صلاحيات التشغيل")

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
print("Mandatory runtime setup merged")
namespace = {"__name__": "__main__", "__file__": str(TWO_MINUTE_TOOL)}
exec(compile(TWO_MINUTE_TOOL.read_text(encoding="utf-8"), str(TWO_MINUTE_TOOL), "exec"), namespace)
