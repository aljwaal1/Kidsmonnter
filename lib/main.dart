import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
      ),
      home: const Directionality(
        textDirection: TextDirection.rtl,
        child: HomeScreen(),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _channel = MethodChannel('kidsmonnter/control');
  static const _durationOptions = <int>[10, 30, 60, 90, 120, 180];

  int _dailyMinutes = 60;
  int _usedSeconds = 0;
  int _failedAttempts = 0;
  bool _enabled = false;
  bool _overlayAllowed = false;
  bool _hasPin = false;
  bool _loading = true;
  bool _savingDuration = false;
  String _parentEmail = '';
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadStatus();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 2),
      (_) => _loadStatus(silent: true),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadStatus({bool silent = false}) async {
    try {
      final status = await _channel.invokeMapMethod<String, dynamic>('getStatus');
      final overlay = await _channel.invokeMethod<bool>('canDrawOverlays') ?? false;
      if (!mounted || status == null) return;
      setState(() {
        _enabled = status['enabled'] == true;
        _usedSeconds = (status['usedSeconds'] as num?)?.toInt() ?? 0;
        _dailyMinutes = (status['dailyMinutes'] as num?)?.toInt() ?? 60;
        _failedAttempts = (status['failedAttempts'] as num?)?.toInt() ?? 0;
        _hasPin = status['hasPin'] == true;
        _parentEmail = status['parentEmail']?.toString() ?? '';
        _overlayAllowed = overlay;
        _loading = false;
      });
    } on PlatformException catch (error) {
      if (!silent) _message('تعذر قراءة حالة الحماية: ${error.message ?? ''}');
      if (mounted) setState(() => _loading = false);
    }
  }

  void _message(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }

  Future<String?> _askPin({required String title, bool confirm = false}) async {
    final first = TextEditingController();
    final second = TextEditingController();
    String? error;
    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
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
              if (error != null) ...[
                const SizedBox(height: 10),
                Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إلغاء'),
            ),
            FilledButton(
              onPressed: () {
                final pin = first.text.trim();
                if (pin.length != 6 || int.tryParse(pin) == null) {
                  setDialogState(() => error = 'أدخل 6 أرقام صحيحة.');
                  return;
                }
                if (confirm && pin != second.text.trim()) {
                  setDialogState(() => error = 'الرمزان غير متطابقين.');
                  return;
                }
                Navigator.pop(context, pin);
              },
              child: const Text('متابعة'),
            ),
          ],
        ),
      ),
    );
  }

  Future<bool> _ensurePin() async {
    if (_hasPin) return true;
    final pin = await _askPin(title: 'إنشاء رمز ولي الأمر', confirm: true);
    if (pin == null) return false;
    try {
      await _channel.invokeMethod('setPin', {'pin': pin});
      await _loadStatus();
      _message('تم حفظ رمز ولي الأمر.');
      return true;
    } on PlatformException catch (error) {
      _message(error.message ?? 'تعذر حفظ الرمز.');
      return false;
    }
  }

  Future<void> _setProtection(bool value) async {
    if (value) {
      if (!await _ensurePin()) return;
      if (!_overlayAllowed) {
        await _channel.invokeMethod('openOverlaySettings');
        _message('فعّل الظهور فوق التطبيقات، ثم ارجع واضغط تفعيل.');
        return;
      }
      await _channel.invokeMethod('startProtection', {'minutes': _dailyMinutes});
    } else {
      final pin = await _askPin(title: 'إيقاف الحماية');
      if (pin == null) return;
      try {
        await _channel.invokeMethod('stopProtection', {'pin': pin});
      } on PlatformException {
        _message('رمز ولي الأمر غير صحيح، وتم تسجيل المحاولة.');
      }
    }
    await _loadStatus();
  }

  Future<void> _changeDuration(int minutes) async {
    if (_savingDuration || minutes == _dailyMinutes) return;
    if (!await _ensurePin()) return;

    final pin = await _askPin(title: 'تأكيد اختيار ${_durationLabel(minutes)}');
    if (pin == null) return;

    setState(() => _savingDuration = true);
    try {
      final valid = await _channel.invokeMethod<bool>('verifyPin', {'pin': pin}) ?? false;
      if (!valid) {
        _message('رمز ولي الأمر غير صحيح، وتم تسجيل المحاولة.');
        return;
      }

      final wasEnabled = _enabled;
      await _channel.invokeMethod('startProtection', {'minutes': minutes});
      if (!wasEnabled) {
        await _channel.invokeMethod('stopProtection', {'pin': pin});
      }

      await _loadStatus();
      _message('تم اعتماد ${_durationLabel(minutes)} يوميًا.');
    } on PlatformException catch (error) {
      _message(error.message ?? 'تعذر حفظ المدة.');
    } finally {
      if (mounted) setState(() => _savingDuration = false);
    }
  }

  Future<void> _addTime(int minutes) async {
    final pin = await _askPin(title: 'إضافة $minutes دقيقة');
    if (pin == null) return;
    try {
      await _channel.invokeMethod('addTime', {'pin': pin, 'minutes': minutes});
      _message('تمت إضافة $minutes دقيقة.');
    } on PlatformException {
      _message('رمز ولي الأمر غير صحيح، وتم تسجيل المحاولة.');
    }
    await _loadStatus();
  }

  Future<void> _editParentEmail() async {
    if (!await _ensurePin()) return;
    final pin = await _askPin(title: 'تأكيد تغيير البريد');
    if (pin == null) return;
    final valid = await _channel.invokeMethod<bool>('verifyPin', {'pin': pin}) ?? false;
    if (!valid) {
      _message('رمز ولي الأمر غير صحيح.');
      return;
    }

    final controller = TextEditingController(text: _parentEmail);
    final email = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('بريد ولي الأمر'),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.emailAddress,
          textDirection: TextDirection.ltr,
          decoration: const InputDecoration(labelText: 'البريد الإلكتروني'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('إلغاء')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('حفظ'),
          ),
        ],
      ),
    );
    if (email == null || email.isEmpty) return;
    try {
      await _channel.invokeMethod('setParentEmail', {'email': email});
      await _loadStatus();
      _message('تم حفظ البريد.');
    } on PlatformException catch (error) {
      _message(error.message ?? 'تعذر حفظ البريد.');
    }
  }

  Future<void> _showFailedAttempts() async {
    final raw = await _channel.invokeListMethod<dynamic>('getFailedAttempts') ?? const [];
    if (!mounted) return;
    final attempts = raw.whereType<Map>().toList();
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('المحاولات الفاشلة'),
        content: SizedBox(
          width: double.maxFinite,
          child: attempts.isEmpty
              ? const Text('لا توجد محاولات مسجلة.')
              : ListView.builder(
                  shrinkWrap: true,
                  itemCount: attempts.length,
                  itemBuilder: (_, index) => ListTile(
                    dense: true,
                    leading: const Icon(Icons.warning_amber_rounded),
                    title: Text(attempts[index]['source']?.toString() ?? ''),
                    subtitle: Text(
                      attempts[index]['time']?.toString() ?? '',
                      textDirection: TextDirection.ltr,
                    ),
                  ),
                ),
        ),
        actions: [
          if (attempts.isNotEmpty)
            TextButton.icon(
              onPressed: () {
                Navigator.pop(context);
                _channel.invokeMethod('sendSecurityReport');
              },
              icon: const Icon(Icons.email_outlined),
              label: const Text('إرسال التقرير'),
            ),
          FilledButton(onPressed: () => Navigator.pop(context), child: const Text('إغلاق')),
        ],
      ),
    );
  }

  int get _limitSeconds => _dailyMinutes * 60;
  int get _remainingSeconds => (_limitSeconds - _usedSeconds).clamp(0, _limitSeconds);

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
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final scheme = Theme.of(context).colorScheme;
    final progress = _limitSeconds == 0
        ? 0.0
        : (_remainingSeconds / _limitSeconds).clamp(0.0, 1.0);

    return Scaffold(
      appBar: AppBar(
        title: const Text('حارس وقت الأطفال'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _enabled ? scheme.primaryContainer : scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  Icon(
                    _enabled ? Icons.shield : Icons.shield_outlined,
                    size: 42,
                    color: _enabled ? scheme.primary : scheme.outline,
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _enabled ? 'الحماية مفعّلة' : 'الحماية متوقفة',
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _enabled
                              ? 'العداد يعمل تلقائيًا أثناء استخدام الهاتف.'
                              : 'اختر المدة ثم فعّل الحماية.',
                        ),
                      ],
                    ),
                  ),
                  Switch(value: _enabled, onChanged: _setProtection),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Column(
                  children: [
                    Text('المدة المعتمدة: ${_durationLabel(_dailyMinutes)}'),
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
                    Text('المستخدم اليوم: ${_format(_usedSeconds)}'),
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
                final selected = _dailyMinutes == minutes;
                return ChoiceChip(
                  label: Text(_durationLabel(minutes)),
                  selected: selected,
                  onSelected: _savingDuration ? null : (_) => _changeDuration(minutes),
                );
              }).toList(),
            ),
            if (_savingDuration) ...[
              const SizedBox(height: 10),
              const LinearProgressIndicator(),
            ],
            const SizedBox(height: 18),
            Card(
              child: ListTile(
                leading: Icon(_hasPin ? Icons.lock : Icons.lock_open),
                title: Text(_hasPin ? 'رمز ولي الأمر محفوظ' : 'أنشئ رمز ولي الأمر'),
                subtitle: const Text('مطلوب لتغيير المدة أو إيقاف الحماية.'),
                trailing: FilledButton.tonal(
                  onPressed: _ensurePin,
                  child: Text(_hasPin ? 'محفوظ' : 'إنشاء'),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(Icons.alternate_email),
                title: const Text('بريد ولي الأمر'),
                subtitle: Text(
                  _parentEmail.isEmpty ? 'لم يتم تحديد بريد.' : _parentEmail,
                  textDirection: TextDirection.ltr,
                ),
                onTap: _editParentEmail,
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: Badge(
                  isLabelVisible: _failedAttempts > 0,
                  label: Text('$_failedAttempts'),
                  child: const Icon(Icons.gpp_maybe_outlined),
                ),
                title: const Text('المحاولات الفاشلة'),
                subtitle: Text('عدد المحاولات: $_failedAttempts'),
                onTap: _showFailedAttempts,
              ),
            ),
            if (_enabled) ...[
              const SizedBox(height: 18),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('إضافة وقت', style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [10, 15, 30, 60]
                            .map(
                              (minutes) => OutlinedButton(
                                onPressed: () => _addTime(minutes),
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
                  _overlayAllowed ? Icons.check_circle : Icons.warning_amber_rounded,
                  color: _overlayAllowed ? Colors.green : Colors.orange,
                ),
                title: Text(
                  _overlayAllowed
                      ? 'صلاحية شاشة القفل مفعّلة'
                      : 'صلاحية شاشة القفل مطلوبة',
                ),
                subtitle: const Text('ضرورية لإظهار القفل عند انتهاء الوقت.'),
                trailing: _overlayAllowed
                    ? null
                    : FilledButton.tonal(
                        onPressed: () => _channel.invokeMethod('openOverlaySettings'),
                        child: const Text('تفعيل'),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
