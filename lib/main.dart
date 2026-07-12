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

  int _dailyMinutes = 60;
  int _usedSeconds = 0;
  bool _enabled = false;
  bool _overlayAllowed = false;
  bool _loading = true;
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
        _overlayAllowed = overlay;
        _loading = false;
      });
    } on PlatformException catch (error) {
      if (!silent && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تعذر قراءة حالة الحماية: ${error.message ?? ''}')),
        );
      }
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _setProtection(bool value) async {
    if (value && !_overlayAllowed) {
      await _channel.invokeMethod('openOverlaySettings');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('فعّل السماح بالظهور فوق التطبيقات، ثم ارجع واضغط تفعيل.'),
          ),
        );
      }
      return;
    }

    try {
      if (value) {
        await _channel.invokeMethod('startProtection', {'minutes': _dailyMinutes});
      } else {
        await _channel.invokeMethod('stopProtection');
      }
      await _loadStatus();
    } on PlatformException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('لم يتم تنفيذ الطلب: ${error.message ?? ''}')),
      );
    }
  }

  Future<void> _changeDuration(int minutes) async {
    if (_enabled) {
      final approved = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('تغيير الوقت اليومي'),
          content: const Text(
            'سيتم تطبيق المدة الجديدة فورًا. الوقت المستخدم اليوم لن يُحذف.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('إلغاء'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('تطبيق'),
            ),
          ],
        ),
      );
      if (approved != true) return;
    }

    setState(() => _dailyMinutes = minutes);
    if (_enabled) {
      await _channel.invokeMethod('startProtection', {'minutes': minutes});
      await _loadStatus();
    }
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
    if (minutes == 30) return '30 دقيقة';
    if (minutes == 60) return 'ساعة';
    if (minutes == 90) return 'ساعة ونصف';
    if (minutes == 120) return 'ساعتان';
    return '3 ساعات';
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
                              ? 'يُحسب وقت الشاشة تلقائيًا لجميع التطبيقات.'
                              : 'فعّل الحماية لبدء احتساب استخدام الهاتف.',
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
                    const Text('الوقت المتبقي اليوم'),
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
            const SizedBox(height: 22),
            const Text(
              'المدة اليومية',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [30, 60, 90, 120, 180].map((minutes) {
                return ChoiceChip(
                  label: Text(_durationLabel(minutes)),
                  selected: _dailyMinutes == minutes,
                  onSelected: (_) => _changeDuration(minutes),
                );
              }).toList(),
            ),
            const SizedBox(height: 22),
            Card(
              child: ListTile(
                leading: Icon(
                  _overlayAllowed ? Icons.check_circle : Icons.warning_amber_rounded,
                  color: _overlayAllowed ? Colors.green : Colors.orange,
                ),
                title: Text(
                  _overlayAllowed ? 'صلاحية شاشة القفل مفعّلة' : 'صلاحية شاشة القفل مطلوبة',
                ),
                subtitle: const Text(
                  'هذه الصلاحية ضرورية لإظهار شاشة انتهاء الوقت فوق جميع التطبيقات.',
                ),
                trailing: _overlayAllowed
                    ? null
                    : FilledButton.tonal(
                        onPressed: () => _channel.invokeMethod('openOverlaySettings'),
                        child: const Text('تفعيل'),
                      ),
              ),
            ),
            const SizedBox(height: 10),
            const Card(
              child: ListTile(
                leading: Icon(Icons.notifications_active_outlined),
                title: Text('تنبيهات تلقائية'),
                subtitle: Text('تنبيه قبل 5 دقائق، وتنبيه أخير قبل دقيقة.'),
              ),
            ),
            const SizedBox(height: 10),
            const Card(
              child: ListTile(
                leading: Icon(Icons.restart_alt),
                title: Text('يعمل بعد إعادة التشغيل'),
                subtitle: Text('تعود خدمة الحماية تلقائيًا إذا كانت مفعّلة.'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
