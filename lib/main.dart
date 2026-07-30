import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'guard_diagnostics_action.dart';
import 'guard_diagnostics_card.dart';
import 'guard_diagnostics_controller.dart';
import 'guard_status.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const KidsMonnterApp());
}

class KidsMonnterApp extends StatelessWidget {
  const KidsMonnterApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'حارس وقت الأطفال',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF315F57),
        scaffoldBackgroundColor: const Color(0xFFF4F7F5),
        cardTheme: const CardThemeData(
          margin: EdgeInsets.zero,
          clipBehavior: Clip.antiAlias,
        ),
      ),
      home: const Directionality(
        textDirection: TextDirection.rtl,
        child: HomeScreen(),
      ),
    );
  }
}

class DevicePolicyStatus {
  const DevicePolicyStatus({
    required this.deviceOwner,
    required this.adminActive,
    required this.lockTaskPermitted,
    required this.uninstallBlocked,
  });

  final bool deviceOwner;
  final bool adminActive;
  final bool lockTaskPermitted;
  final bool uninstallBlocked;

  factory DevicePolicyStatus.fromMap(Map<String, dynamic>? map) {
    return DevicePolicyStatus(
      deviceOwner: map?['deviceOwner'] == true,
      adminActive: map?['adminActive'] == true,
      lockTaskPermitted: map?['lockTaskPermitted'] == true,
      uninstallBlocked: map?['uninstallBlocked'] == true,
    );
  }

  bool get uninstallProtectionActive =>
      deviceOwner && adminActive && uninstallBlocked;
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  static const MethodChannel _channel = MethodChannel('kidsmonnter/control');
  // TWO_MINUTE_DURATION_MARKER
  static const List<int> _durationOptions = <int>[2, 10, 30, 60, 90, 120, 180];

  GuardStatus? _status;
  DevicePolicyStatus _devicePolicy = const DevicePolicyStatus(
    deviceOwner: false,
    adminActive: false,
    lockTaskPermitted: false,
    uninstallBlocked: false,
  );
  Timer? _refreshTimer;
  bool _busy = false;
  String? _error;
  bool _exactAlarmAllowed = false;
  bool _batteryOptimizationIgnored = false;
  bool _uninstallGuardEnabled = false;

  late final GuardDiagnosticsController _diagnosticsController =
      GuardDiagnosticsController(
    channel: _channel,
    refreshStatus: _refreshStatus,
  );

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refreshStatus();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _refreshStatus(silent: true),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshStatus();
    }
  }

  Future<void> _refreshStatus({bool silent = false}) async {
    try {
      final map = await _channel.invokeMapMethod<String, dynamic>('getStatus');
      final policyMap = await _channel
          .invokeMapMethod<String, dynamic>('getDevicePolicyStatus');
      if (!mounted || map == null) return;

      final overlay = map['overlayAllowed'] == true ||
          (await _channel.invokeMethod<bool>('canDrawOverlays') ?? false);
      setState(() {
        _status = GuardStatus.fromMap(map, overlay);
        _devicePolicy = DevicePolicyStatus.fromMap(policyMap);
        _exactAlarmAllowed = map['exactAlarmAllowed'] == true;
        _batteryOptimizationIgnored = map['batteryOptimizationIgnored'] == true;
        _uninstallGuardEnabled = map['uninstallGuardEnabled'] == true;
        _error = null;
      });
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message ?? 'تعذر قراءة حالة الحماية.');
      if (!silent) _showMessage(_error!);
    }
  }

  Future<T?> _runBusy<T>(Future<T> Function() action) async {
    if (_busy) return null;
    setState(() => _busy = true);
    try {
      return await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showMessage(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }

  Future<String?> _askPin({required String title, bool confirm = false}) async {
    final first = TextEditingController();
    final second = TextEditingController();
    String? validationError;

    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(title),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: first,
                autofocus: true,
                keyboardType: TextInputType.number,
                obscureText: true,
                maxLength: 6,
                textDirection: TextDirection.ltr,
                decoration: const InputDecoration(
                  labelText: 'PIN من 6 أرقام',
                  counterText: '',
                ),
              ),
              if (confirm) ...[
                const SizedBox(height: 10),
                TextField(
                  controller: second,
                  keyboardType: TextInputType.number,
                  obscureText: true,
                  maxLength: 6,
                  textDirection: TextDirection.ltr,
                  decoration: const InputDecoration(
                    labelText: 'تأكيد PIN',
                    counterText: '',
                  ),
                ),
              ],
              if (validationError != null) ...[
                const SizedBox(height: 8),
                Text(
                  validationError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('إلغاء'),
            ),
            FilledButton(
              onPressed: () {
                final pin = first.text.trim();
                if (pin.length != 6 || int.tryParse(pin) == null) {
                  setDialogState(() => validationError = 'أدخل 6 أرقام صحيحة.');
                  return;
                }
                if (confirm && pin != second.text.trim()) {
                  setDialogState(
                      () => validationError = 'الرمزان غير متطابقين.');
                  return;
                }
                Navigator.pop(dialogContext, pin);
              },
              child: const Text('متابعة'),
            ),
          ],
        ),
      ),
    );

    first.dispose();
    second.dispose();
    return result;
  }

  Future<bool> _ensurePin() async {
    if (_status?.hasPin == true) return true;
    final pin = await _askPin(title: 'إنشاء رمز ولي الأمر', confirm: true);
    if (pin == null) return false;
    try {
      await _channel.invokeMethod('setPin', {'pin': pin});
      await _refreshStatus();
      _showMessage('تم حفظ رمز ولي الأمر بصورة آمنة.');
      return true;
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر حفظ الرمز.');
      return false;
    }
  }

  // MANDATORY_RUNTIME_SETUP_MARKER
  // MANDATORY_DEVICE_OWNER_SETUP_MARKER
  bool get _runtimeSetupReady =>
      (_status?.overlayAllowed == true) &&
      _exactAlarmAllowed &&
      _batteryOptimizationIgnored &&
      _uninstallGuardEnabled &&
      _devicePolicy.adminActive; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER
  // PARENT_PIN_UNINSTALL_GUARD_MARKER

  Future<void> _activateDeviceAdministrator() async {
    try {
      await _channel.invokeMethod<void>('activateDeviceAdministrator');
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر فتح شاشة تفعيل مسؤول الجهاز.');
    }
  }

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
            const SizedBox(height: 10),
            item(
              ready: _uninstallGuardEnabled,
              title: 'قفل الحذف برمز الأب',
              subtitle: _uninstallGuardEnabled
                  ? 'مفعّل: تتم مقاطعة شاشة حذف التطبيق ويُطلب رمز الأب.'
                  : 'إجباري: فعّل خدمة حارس وقت الأطفال ضمن إمكانية الوصول.',
              action: () => _openRequiredSetting('openAccessibilitySettings'),
              button: 'تفعيل حارس الحذف',
            ),
            const SizedBox(height: 10),
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
    await _runBusy(() async {
      try {
        if (enabled) {
          await _refreshStatus(silent: true);
          if (!_runtimeSetupReady) {
            _showMessage('أكمل صلاحيات الحماية الإلزامية أولًا.');
            return;
          }
          if (!await _ensurePin()) return;
          await _channel.invokeMethod('startProtection', {
            'minutes': _status?.dailyMinutes ?? 10,
          });
          await _refreshStatus();
          _showMessage('تم تفعيل الحماية. احتساب الوقت يستمر خارج التطبيق.');

          if (_status?.overlayAllowed != true) {
            await _channel.invokeMethod('openOverlaySettings');
            _showMessage(
                'امنح صلاحية الظهور فوق التطبيقات حتى تعمل شاشة القفل.');
          }
        } else {
          final pin = await _askPin(title: 'إيقاف الحماية');
          if (pin == null) return;
          await _channel.invokeMethod('stopProtection', {'pin': pin});
          await _refreshStatus();
          _showMessage('تم إيقاف الحماية.');
        }
      } on PlatformException catch (error) {
        await _refreshStatus(silent: true);
        _showMessage(error.message ?? 'تعذر تغيير حالة الحماية.');
      }
    });
  }

  Future<void> _changeDuration(int minutes) async {
    if (minutes == _status?.dailyMinutes) return;
    await _runBusy(() async {
      if (!await _ensurePin()) return;
      final pin =
          await _askPin(title: 'تأكيد اختيار ${_durationLabel(minutes)}');
      if (pin == null) return;

      try {
        final valid =
            await _channel.invokeMethod<bool>('verifyPin', {'pin': pin}) ??
                false;
        if (!valid) {
          _showMessage('رمز ولي الأمر غير صحيح، وتم تسجيل المحاولة.');
          return;
        }

        // DURATION_WITHOUT_PROTECTION_TOGGLE_MARKER
        await _channel.invokeMethod('setDailyMinutes', {
          'pin': pin,
          'minutes': minutes,
        });
        await _refreshStatus();
        _showMessage('تم اعتماد ${_durationLabel(minutes)} يوميًا.');
      } on PlatformException catch (error) {
        _showMessage(error.message ?? 'تعذر حفظ المدة.');
      }
    });
  }

  Future<void> _addTime(int minutes) async {
    await _runBusy(() async {
      final pin = await _askPin(title: 'إضافة $minutes دقيقة');
      if (pin == null) return;
      try {
        await _channel
            .invokeMethod('addTime', {'pin': pin, 'minutes': minutes});
        await _refreshStatus();
        _showMessage('تمت إضافة $minutes دقيقة.');
      } on PlatformException catch (error) {
        _showMessage(error.message ?? 'رمز ولي الأمر غير صحيح.');
      }
    });
  }

  Future<void> _editParentEmail() async {
    if (!await _ensurePin()) return;
    final pin = await _askPin(title: 'تأكيد تغيير البريد');
    if (pin == null) return;

    final valid =
        await _channel.invokeMethod<bool>('verifyPin', {'pin': pin}) ?? false;
    if (!valid) {
      _showMessage('رمز ولي الأمر غير صحيح.');
      return;
    }

    final controller = TextEditingController(text: _status?.parentEmail ?? '');
    final email = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('بريد ولي الأمر'),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.emailAddress,
          textDirection: TextDirection.ltr,
          decoration: const InputDecoration(labelText: 'البريد الإلكتروني'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('حفظ'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (email == null) return;

    try {
      await _channel.invokeMethod('setParentEmail', {'email': email});
      await _refreshStatus();
      _showMessage(email.isEmpty ? 'تم حذف البريد.' : 'تم حفظ البريد.');
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر حفظ البريد.');
    }
  }

  // DAILY_FAILED_ATTEMPT_REPORTS_MARKER
  Future<void> _showFailedAttempts() async {
    final raw = await _channel.invokeListMethod<dynamic>('getFailedAttempts') ??
        const [];
    if (!mounted) return;

    final attempts = raw.whereType<Map>().map((item) {
      final time = item['time']?.toString() ?? '';
      final date = item['date']?.toString() ??
          (time.contains(' ') ? time.split(' ').first : 'غير معروف');
      final clock = item['clock']?.toString() ??
          (time.contains(' ') ? time.substring(time.indexOf(' ') + 1) : time);
      return <String, String>{
        'date': date,
        'clock': clock,
        'source': item['source']?.toString() ?? '',
      };
    }).toList();

    final grouped = <String, List<Map<String, String>>>{};
    for (final attempt in attempts) {
      grouped.putIfAbsent(attempt['date']!, () => []).add(attempt);
    }

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('التقارير اليومية للمحاولات الخاطئة'),
        content: SizedBox(
          width: double.maxFinite,
          height: 480,
          child: grouped.isEmpty
              ? const Center(child: Text('لا توجد محاولات خاطئة مسجلة.'))
              : ListView(
                  children: grouped.entries.map((entry) {
                    final dayAttempts = entry.value;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ExpansionTile(
                        initiallyExpanded: entry.key == grouped.keys.first,
                        leading: const Icon(Icons.calendar_month_outlined),
                        title:
                            Text(entry.key, textDirection: TextDirection.ltr),
                        subtitle: Text('${dayAttempts.length} محاولة خاطئة'),
                        children: dayAttempts
                            .map(
                              (attempt) => ListTile(
                                dense: true,
                                leading:
                                    const Icon(Icons.warning_amber_rounded),
                                title: Text(attempt['source'] ?? ''),
                                subtitle: Text(
                                  attempt['clock'] ?? '',
                                  textDirection: TextDirection.ltr,
                                ),
                              ),
                            )
                            .toList(),
                      ),
                    );
                  }).toList(),
                ),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('إغلاق'),
          ),
        ],
      ),
    );
  }

  // RUNTIME_DIAGNOSTICS_UI_MARKER
  Future<void> _showDiagnosticLog() async {
    try {
      final log = await _channel.invokeMethod<String>('getDiagnosticLog') ?? '';
      if (!mounted) return;

      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('سجل تشخيص التطبيق'),
          content: SizedBox(
            width: double.maxFinite,
            height: 480,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Scrollbar(
                  child: SingleChildScrollView(
                    child: SelectableText(
                      log.isEmpty ? 'لا توجد بيانات مسجلة بعد.' : log,
                      textDirection: TextDirection.ltr,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          actions: [
            TextButton.icon(
              onPressed: log.isEmpty
                  ? null
                  : () async {
                      await Clipboard.setData(ClipboardData(text: log));
                      _showMessage('تم نسخ سجل التشخيص.');
                    },
              icon: const Icon(Icons.copy_all_outlined),
              label: const Text('نسخ السجل'),
            ),
            TextButton.icon(
              onPressed: () async {
                await _channel.invokeMethod<void>('clearDiagnosticLog');
                if (dialogContext.mounted) Navigator.pop(dialogContext);
                _showMessage('تم مسح السجل وبدأ تسجيل جديد.');
              },
              icon: const Icon(Icons.delete_sweep_outlined),
              label: const Text('مسح'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر قراءة سجل التشخيص.');
    }
  }

  Future<void> _resolveDiagnosticAction(GuardDiagnosticAction action) async {
    await _runBusy(() async {
      try {
        await _diagnosticsController.resolve(
          action,
          dailyMinutes: _status?.dailyMinutes ?? 10,
        );
        if (action == GuardDiagnosticAction.openOverlaySettings) {
          _showMessage('فعّل صلاحية شاشة القفل ثم ارجع إلى التطبيق.');
        } else if (action == GuardDiagnosticAction.restartProtectionService) {
          _showMessage('تم طلب إعادة تشغيل خدمة الحماية.');
        }
      } on PlatformException catch (error) {
        _showMessage(error.message ?? 'تعذر معالجة مشكلة الحماية.');
      }
    });
  }

  // PARENT_PIN_UNINSTALL_UI_MARKER
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

  Future<void> _configureDeviceOwnerPolicies() async {
    if (!_devicePolicy.deviceOwner) {
      await _showDeviceOwnerInstructions();
      return;
    }

    await _runBusy(() async {
      try {
        await _channel.invokeMethod('configureDeviceOwner');
        await _refreshStatus();
        _showMessage('تم تفعيل سياسات منع الحذف ووضع القفل.');
      } on PlatformException catch (error) {
        _showMessage(error.message ?? 'تعذر تطبيق سياسات الجهاز.');
      }
    });
  }

  Future<void> _showDeviceOwnerInstructions() async {
    const command =
        'adb shell dpm set-device-owner com.explapp.kidstimeguard/.KidsMonnterDeviceAdminReceiver';
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('تفعيل منع الحذف الكامل'),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Android لا يسمح لتطبيق عادي بمنع حذفه. الحماية الكاملة تحتاج إعداد التطبيق كـ Device Owner على جهاز جديد أو بعد إعادة ضبط المصنع.',
              ),
              SizedBox(height: 12),
              Text('بعد تثبيت التطبيق وقبل إضافة حسابات، نفّذ عبر الكمبيوتر:'),
              SizedBox(height: 8),
              SelectableText(
                command,
                textDirection: TextDirection.ltr,
                style: TextStyle(fontFamily: 'monospace'),
              ),
              SizedBox(height: 12),
              Text(
                'عند نجاح الإعداد سيمنع النظام حذف التطبيق، ويسمح بوضع القفل المحكم. لا يمكن تفعيل ذلك بزر داخل التطبيق بسبب قيود Android الأمنية.',
              ),
            ],
          ),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('فهمت'),
          ),
        ],
      ),
    );
  }

  // STRICT_RUNTIME_UI_MARKER
  Future<void> _openStrictSetting(String method) async {
    try {
      await _channel.invokeMethod<void>(method);
    } on PlatformException catch (error) {
      _showMessage(error.message ?? 'تعذر فتح إعداد النظام.');
    }
  }

  Widget _buildStrictRuntimeCard() {
    final ready = _exactAlarmAllowed && _batteryOptimizationIgnored;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(ready ? Icons.verified_user : Icons.warning_amber_rounded),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    ready
                        ? 'استمرارية الخلفية مضبوطة'
                        : 'يلزم تشديد تشغيل الخلفية',
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(_exactAlarmAllowed
                ? 'مراقب الاستعادة الدقيق مفعّل.'
                : 'فعّل المنبهات والتذكيرات حتى يستطيع المراقب إعادة الخدمة.'),
            const SizedBox(height: 6),
            Text(_batteryOptimizationIgnored
                ? 'التطبيق مستثنى من تحسين البطارية.'
                : 'استثنِ التطبيق من تحسين البطارية لمنع النظام من تجميده.'),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!_exactAlarmAllowed)
                  FilledButton.tonal(
                    onPressed: () =>
                        _openStrictSetting('openExactAlarmSettings'),
                    child: const Text('تفعيل المنبه الدقيق'),
                  ),
                if (!_batteryOptimizationIgnored)
                  FilledButton.tonal(
                    onPressed: () =>
                        _openStrictSetting('openBatteryOptimizationSettings'),
                    child: const Text('استثناء البطارية'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  int get _limitSeconds => (_status?.dailyMinutes ?? 10) * 60;
  int get _remainingSeconds =>
      (_limitSeconds - (_status?.usedSeconds ?? 0)).clamp(0, _limitSeconds);

  String _format(int seconds) {
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    final secs = seconds % 60;
    return '${hours.toString().padLeft(2, '0')}:'
        '${minutes.toString().padLeft(2, '0')}:'
        '${secs.toString().padLeft(2, '0')}';
  }

  String _durationLabel(int minutes) {
    switch (minutes) {
      case 2:
        return 'دقيقتان';
      case 10:
        return '10 دقائق';
      case 30:
        return '30 دقيقة';
      case 60:
        return 'ساعة';
      case 90:
        return 'ساعة ونصف';
      case 120:
        return 'ساعتان';
      case 180:
        return '3 ساعات';
      default:
        return '$minutes دقيقة';
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    if (status == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('حارس وقت الأطفال')),
        body: Center(
          child: _error == null
              ? const CircularProgressIndicator()
              : Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!, textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _refreshStatus,
                        child: const Text('إعادة المحاولة'),
                      ),
                    ],
                  ),
                ),
        ),
      );
    }

    if (!_runtimeSetupReady) {
      return _buildMandatorySetupScreen();
    }

    final scheme = Theme.of(context).colorScheme;
    final progress = _limitSeconds == 0
        ? 0.0
        : (_remainingSeconds / _limitSeconds).clamp(0.0, 1.0);

    return Scaffold(
      appBar: AppBar(
        title: const Text('حارس وقت الأطفال'),
        centerTitle: true,
        actions: [
          IconButton(
            tooltip: 'تحديث الحالة',
            onPressed: _busy ? null : _refreshStatus,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_busy) const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: status.enabled
                    ? scheme.primaryContainer
                    : scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  Icon(
                    status.enabled ? Icons.shield : Icons.shield_outlined,
                    size: 42,
                    color: status.enabled ? scheme.primary : scheme.outline,
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          status.enabled ? 'الحماية مفعّلة' : 'الحماية متوقفة',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          status.enabled
                              ? 'الوقت يُحتسب بواسطة خدمة Android حتى عند الخروج من التطبيق.'
                              : 'اختر المدة ثم فعّل الحماية.',
                        ),
                      ],
                    ),
                  ),
                  Switch(
                    value: status.enabled,
                    onChanged: _busy ? null : _setProtection,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _buildStrictRuntimeCard(),
            const SizedBox(height: 14),
            GuardDiagnosticsCard(
              diagnostics: status.diagnostics,
              now: DateTime.now(),
              onResolveIssue: (action) {
                _resolveDiagnosticAction(action);
              },
            ),
            const SizedBox(height: 14),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Column(
                  children: [
                    Text(
                        'المدة المعتمدة: ${_durationLabel(status.dailyMinutes)}'),
                    const SizedBox(height: 10),
                    Text(
                      _format(_remainingSeconds),
                      textDirection: TextDirection.ltr,
                      style: const TextStyle(
                        fontSize: 44,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 18),
                    LinearProgressIndicator(
                      value: progress,
                      minHeight: 10,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    const SizedBox(height: 12),
                    Text('المستخدم اليوم: ${_format(status.usedSeconds)}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text(
              'اختر مدة الاستخدام اليومية',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _durationOptions.map((minutes) {
                return ChoiceChip(
                  label: Text(_durationLabel(minutes)),
                  selected: status.dailyMinutes == minutes,
                  onSelected: _busy ? null : (_) => _changeDuration(minutes),
                );
              }).toList(),
            ),
            const SizedBox(height: 18),
            // DEFAULT_UNINSTALL_PROTECTION_UI_MARKER
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
            Card(
              child: ListTile(
                leading: Icon(status.hasPin ? Icons.lock : Icons.lock_open),
                title: Text(
                  status.hasPin ? 'رمز ولي الأمر محفوظ' : 'أنشئ رمز ولي الأمر',
                ),
                subtitle: const Text('مطلوب لتغيير المدة أو إيقاف الحماية.'),
                trailing: FilledButton.tonal(
                  onPressed: _busy ? null : _ensurePin,
                  child: Text(status.hasPin ? 'محفوظ' : 'إنشاء'),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(Icons.alternate_email),
                title: const Text('بريد ولي الأمر'),
                subtitle: Text(
                  status.parentEmail.isEmpty
                      ? 'لم يتم تحديد بريد.'
                      : status.parentEmail,
                  textDirection: TextDirection.ltr,
                ),
                onTap: _busy ? null : _editParentEmail,
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(Icons.bug_report_outlined),
                title: const Text('سجل تشخيص التطبيق'),
                subtitle: const Text(
                  'يعرض تشغيل الخدمة، احتساب الوقت، المراقب ومحاولات القفل.',
                ),
                trailing: const Icon(Icons.chevron_left),
                onTap: _showDiagnosticLog,
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: Badge(
                  isLabelVisible: status.failedAttempts > 0,
                  label: Text('${status.failedAttempts}'),
                  child: const Icon(Icons.gpp_maybe_outlined),
                ),
                title: const Text('تقارير المحاولات الخاطئة'),
                subtitle:
                    Text('محفوظة يوميًا — المجموع: ${status.failedAttempts}'),
                onTap: _showFailedAttempts,
              ),
            ),
            if (status.enabled) ...[
              const SizedBox(height: 18),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'إضافة وقت',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [10, 15, 30, 60]
                            .map(
                              (minutes) => OutlinedButton(
                                onPressed:
                                    _busy ? null : () => _addTime(minutes),
                                child: Text('+$minutes دقيقة'),
                              ),
                            )
                            .toList(),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 18),
            Card(
              child: ListTile(
                leading: Icon(
                  status.overlayAllowed
                      ? Icons.check_circle
                      : Icons.warning_amber_rounded,
                  color: status.overlayAllowed ? Colors.green : Colors.orange,
                ),
                title: Text(
                  status.overlayAllowed
                      ? 'صلاحية شاشة القفل مفعّلة'
                      : 'صلاحية شاشة القفل مطلوبة',
                ),
                subtitle: Text(
                  status.overlayAllowed
                      ? 'يمكن عرض شاشة القفل عند انتهاء الوقت.'
                      : 'العداد يعمل، لكن القفل لن يظهر قبل منح الصلاحية.',
                ),
                trailing: status.overlayAllowed
                    ? null
                    : FilledButton.tonal(
                        onPressed: _busy
                            ? null
                            : () => _channel
                                .invokeMethod<void>('openOverlaySettings'),
                        child: const Text('تفعيل'),
                      ),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
