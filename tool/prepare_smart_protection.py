from pathlib import Path
import re

MAIN = Path('lib/main.dart')
KOTLIN = Path('native/MainActivityV2.kt')
MANIFEST = Path('native/AndroidManifest.xml')

main = MAIN.read_text(encoding='utf-8')
kotlin = KOTLIN.read_text(encoding='utf-8')
manifest = MANIFEST.read_text(encoding='utf-8')

# Remove Device Admin from the distributable build; keep Accessibility available but user-controlled.
manifest = re.sub(
    r'\s*<receiver\s+android:name="\.KidsMonnterDeviceAdminReceiver".*?</receiver>',
    '',
    manifest,
    flags=re.S,
)
manifest = re.sub(
    r'(<service\s+android:name="\.UninstallGuardAccessibilityService".*?android:exported=")false(".*?</service>)',
    r'\1true\2',
    manifest,
    count=1,
    flags=re.S,
)
MANIFEST.write_text(manifest, encoding='utf-8')

# ---------- Flutter smart-mode UI ----------
if 'SMART_PROTECTION_MODE_UI' not in main:
    main = main.replace(
        '  bool _uninstallGuardEnabled = false;\n',
        '  bool _uninstallGuardEnabled = false;\n'
        '  String _protectionMode = \'unset\'; // SMART_PROTECTION_MODE_UI\n',
        1,
    )
    main = main.replace(
        "        _uninstallGuardEnabled = map['uninstallGuardEnabled'] == true;\n",
        "        _uninstallGuardEnabled = map['uninstallGuardEnabled'] == true;\n"
        "        _protectionMode = map['protectionMode']?.toString() ?? 'unset';\n",
        1,
    )

    mode_ui = r'''
  bool get _maximumProtection => _protectionMode == 'maximum';

  Future<void> _selectProtectionMode(String mode) async {
    await _runBusy(() async {
      if (!await _ensurePin()) return;
      try {
        await _channel.invokeMethod<void>('setProtectionMode', {'mode': mode});
        await _refreshStatus();
        if (mode == 'maximum') {
          _showMessage('اختر خدمة «حارس حذف التطبيق» وفعّلها، ثم ارجع إلى التطبيق.');
          await _channel.invokeMethod<void>('openAccessibilitySettings');
        } else {
          _showMessage('تم اختيار الحماية العادية. يمكن تغيير المستوى لاحقًا من التطبيق.');
        }
      } on PlatformException catch (error) {
        _showMessage(error.message ?? 'تعذر حفظ مستوى الحماية.');
      }
    });
  }

  Widget _buildProtectionModeScreen() {
    Widget option({
      required IconData icon,
      required String title,
      required String subtitle,
      required String button,
      required String mode,
      required bool recommended,
    }) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(icon, size: 34),
                const SizedBox(width: 12),
                Expanded(child: Text(title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold))),
                if (recommended) const Chip(label: Text('موصى به')),
              ]),
              const SizedBox(height: 10),
              Text(subtitle),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonal(
                  onPressed: _busy ? null : () => _selectProtectionMode(mode),
                  child: Text(button),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('اختر مستوى الحماية')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            const Icon(Icons.shield_outlined, size: 64),
            const SizedBox(height: 12),
            const Text(
              'اختر مستوى الحماية المناسب لهذا الجهاز',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'يمكن تغيير المستوى لاحقًا بعد إدخال رمز ولي الأمر.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            option(
              icon: Icons.phone_android,
              title: 'حماية عادية',
              subtitle: 'تشغيل العداد والقفل والخدمة الخلفية دون استخدام إمكانية الوصول. التثبيت أبسط، لكن يمكن حذف التطبيق من إعدادات Android.',
              button: 'استخدام الحماية العادية',
              mode: 'normal',
              recommended: true,
            ),
            const SizedBox(height: 14),
            option(
              icon: Icons.admin_panel_settings,
              title: 'حماية قصوى',
              subtitle: 'تفعيل حارس حذف التطبيق عبر إمكانية الوصول، واعتراض شاشة الحذف ومعلومات التطبيق وطلب رمز ولي الأمر. قد يعرض Android تحذيرًا لأن APK مثبت خارج المتجر.',
              button: 'استخدام الحماية القصوى',
              mode: 'maximum',
              recommended: false,
            ),
          ],
        ),
      ),
    );
  }

'''
    main = main.replace('  // MANDATORY_RUNTIME_SETUP_MARKER\n', mode_ui + '  // MANDATORY_RUNTIME_SETUP_MARKER\n', 1)

# Runtime gate: normal mode does not require Accessibility; maximum mode does.
main = re.sub(
    r'bool get _runtimeSetupReady =>.*?;\s*// MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER',
    "bool get _runtimeSetupReady => !_maximumProtection || _uninstallGuardEnabled; // FINAL_SMART_MODE_GATE",
    main,
    count=1,
    flags=re.S,
)

# Replace old mandatory setup with a focused maximum-mode screen.
main = main.replace("      appBar: AppBar(title: const Text('إعداد الحماية الإجباري')),", "      appBar: AppBar(title: const Text('إعداد الحماية القصوى')),", 1)
main = main.replace("'لا يمكن استخدام التطبيق قبل إكمال صلاحيات الحماية'", "'فعّل حارس الحذف لإكمال الحماية القصوى'", 1)

# Show mode chooser before any setup gate.
needle = "    if (!_runtimeSetupReady) {\n      return _buildMandatorySetupScreen();\n    }"
replacement = "    if (_protectionMode == 'unset') {\n      return _buildProtectionModeScreen();\n    }\n\n    if (!_runtimeSetupReady) {\n      return _buildMandatorySetupScreen();\n    }"
if needle not in main:
    raise SystemExit('Flutter build gate not found')
main = main.replace(needle, replacement, 1)
MAIN.write_text(main, encoding='utf-8')

# ---------- Native Android smart-mode logic ----------
if 'PROTECTION_MODE_KEY' not in kotlin:
    kotlin = kotlin.replace(
        'private const val SETTINGS_AUTH_WINDOW_MS = 90_000L\n',
        'private const val SETTINGS_AUTH_WINDOW_MS = 90_000L\n'
        'private const val PROTECTION_MODE_KEY = "protection_mode"\n'
        'private const val PROTECTION_MODE_NORMAL = "normal"\n'
        'private const val PROTECTION_MODE_MAXIMUM = "maximum"\n',
        1,
    )

# Remove Device Admin and Overlay from start requirements; conditionally require Accessibility.
kotlin = re.sub(
    r'\s*// MANDATORY_DEVICE_OWNER_SETUP_MARKER\s*val missing = mutableListOf<String>\(\)\s*// MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER\s*val dpm = getSystemService\(Context\.DEVICE_POLICY_SERVICE\) as DevicePolicyManager\s*val admin = ComponentName\(this, KidsMonnterDeviceAdminReceiver::class\.java\)\s*if \(!dpm\.isAdminActive\(admin\)\) missing\.add\("device_admin"\)',
    '\n                    val missing = mutableListOf<String>()\n                    val protectionMode = prefs.getString(PROTECTION_MODE_KEY, PROTECTION_MODE_NORMAL) ?: PROTECTION_MODE_NORMAL',
    kotlin,
    count=1,
    flags=re.S,
)
kotlin = kotlin.replace(
    '                    if (!isUninstallGuardAccessibilityEnabled()) missing.add("uninstall_guard")\n',
    '                    if (protectionMode == PROTECTION_MODE_MAXIMUM && !isUninstallGuardAccessibilityEnabled()) {\n'
    '                        missing.add("uninstall_guard")\n'
    '                    }\n',
    1,
)
kotlin = kotlin.replace('                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")\n', '', 1)

# Add MethodChannel mode setter before startProtection.
if '"setProtectionMode" -> {' not in kotlin:
    marker = '                // MANDATORY_RUNTIME_SETUP_MARKER\n                "startProtection" -> {'
    block = '''                "setProtectionMode" -> {
                    val mode = call.argument<String>("mode").orEmpty()
                    if (mode != PROTECTION_MODE_NORMAL && mode != PROTECTION_MODE_MAXIMUM) {
                        result.error("INVALID_PROTECTION_MODE", "مستوى الحماية غير صحيح", null)
                    } else {
                        prefs.edit().putString(PROTECTION_MODE_KEY, mode).commit()
                        appendGuardLog("PROTECTION_MODE_CHANGED", "mode=$mode")
                        result.success(true)
                    }
                }
                // MANDATORY_RUNTIME_SETUP_MARKER
                "startProtection" -> {'''
    if marker not in kotlin:
        raise SystemExit('Native startProtection marker not found')
    kotlin = kotlin.replace(marker, block, 1)

# Expose mode to Flutter.
status_line = '                        "uninstallGuardEnabled" to isUninstallGuardAccessibilityEnabled()\n'
if status_line in kotlin and '"protectionMode" to prefs.getString' not in kotlin:
    kotlin = kotlin.replace(
        status_line,
        '                        "uninstallGuardEnabled" to isUninstallGuardAccessibilityEnabled(),\n'
        '                        "protectionMode" to prefs.getString(PROTECTION_MODE_KEY, "unset")\n',
        1,
    )

# Accessibility guard is inert in normal mode.
service_needle = '        val prefs = guardPrefs()\n        if (!hasStoredPin(prefs)) return\n'
service_replacement = '        val prefs = guardPrefs()\n        if (prefs.getString(PROTECTION_MODE_KEY, PROTECTION_MODE_NORMAL) != PROTECTION_MODE_MAXIMUM) return\n        if (!hasStoredPin(prefs)) return\n'
if service_needle not in kotlin:
    raise SystemExit('Accessibility event guard marker not found')
kotlin = kotlin.replace(service_needle, service_replacement, 1)

# Do not reapply Device Owner policies in this distributable build.
kotlin = kotlin.replace('        ensureUninstallProtection()\n        MethodChannel(', '        MethodChannel(', 1)
kotlin = kotlin.replace('                    ensureUninstallProtection()\n                    appendGuardLog("PROTECTION_ENABLED"', '                    appendGuardLog("PROTECTION_ENABLED"', 1)
KOTLIN.write_text(kotlin, encoding='utf-8')

checks = {
    'smart Flutter UI': 'SMART_PROTECTION_MODE_UI' in main,
    'mode chooser': '_buildProtectionModeScreen' in main,
    'native mode setter': '"setProtectionMode" -> {' in kotlin,
    'mode returned': '"protectionMode" to prefs.getString' in kotlin,
    'conditional guard requirement': 'protectionMode == PROTECTION_MODE_MAXIMUM' in kotlin,
    'normal mode disables interception': '!= PROTECTION_MODE_MAXIMUM) return' in kotlin,
    'device admin removed': 'KidsMonnterDeviceAdminReceiver' not in manifest,
    'accessibility retained': 'UninstallGuardAccessibilityService' in manifest,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Smart protection preparation failed: ' + ', '.join(failed))
