import 'dart:async';

import 'package:flutter/material.dart';

void main() {
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
        colorSchemeSeed: const Color(0xFF4F7C72),
        scaffoldBackgroundColor: const Color(0xFFF5F7F6),
      ),
      home: const Directionality(
        textDirection: TextDirection.rtl,
        child: DailyTimeScreen(),
      ),
    );
  }
}

class DailyTimeScreen extends StatefulWidget {
  const DailyTimeScreen({super.key});

  @override
  State<DailyTimeScreen> createState() => _DailyTimeScreenState();
}

class _DailyTimeScreenState extends State<DailyTimeScreen> {
  int _selectedMinutes = 60;
  int _remainingSeconds = 60 * 60;
  Timer? _timer;
  bool _isRunning = false;
  bool _fiveMinuteWarningShown = false;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _setDailyMinutes(int minutes) {
    _timer?.cancel();
    setState(() {
      _selectedMinutes = minutes;
      _remainingSeconds = minutes * 60;
      _isRunning = false;
      _fiveMinuteWarningShown = false;
    });
  }

  void _toggleTimer() {
    if (_isRunning) {
      _timer?.cancel();
      setState(() => _isRunning = false);
      return;
    }

    if (_remainingSeconds <= 0) {
      return;
    }

    setState(() => _isRunning = true);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_remainingSeconds <= 1) {
        timer.cancel();
        setState(() {
          _remainingSeconds = 0;
          _isRunning = false;
        });
        _showTimeFinishedDialog();
        return;
      }

      setState(() => _remainingSeconds--);

      if (_remainingSeconds <= 300 && !_fiveMinuteWarningShown) {
        _fiveMinuteWarningShown = true;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            duration: Duration(seconds: 8),
            content: Text(
              'تبقّى 5 دقائق فقط من وقت استخدام الهاتف اليوم.',
              textAlign: TextAlign.center,
            ),
          ),
        );
      }
    });
  }

  void _resetTimer() {
    _timer?.cancel();
    setState(() {
      _remainingSeconds = _selectedMinutes * 60;
      _isRunning = false;
      _fiveMinuteWarningShown = false;
    });
  }

  Future<void> _showTimeFinishedDialog() async {
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('انتهى وقت الهاتف'),
        content: const Text(
          'انتهى وقت استخدام الهاتف لهذا اليوم. يحتاج فتحه إلى موافقة ولي الأمر.',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('حسنًا'),
          ),
        ],
      ),
    );
  }

  String get _formattedRemaining {
    final hours = _remainingSeconds ~/ 3600;
    final minutes = (_remainingSeconds % 3600) ~/ 60;
    final seconds = _remainingSeconds % 60;
    return '${hours.toString().padLeft(2, '0')}:'
        '${minutes.toString().padLeft(2, '0')}:'
        '${seconds.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('حارس وقت الأطفال'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text(
              'وقت الهاتف اليومي',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'جميع التطبيقات تُحسب من رصيد واحد للهاتف بالكامل.',
              style: TextStyle(fontSize: 15),
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    const Text('الوقت المتبقي اليوم'),
                    const SizedBox(height: 12),
                    Text(
                      _formattedRemaining,
                      textDirection: TextDirection.ltr,
                      style: const TextStyle(
                        fontSize: 42,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: _toggleTimer,
                            icon: Icon(
                              _isRunning ? Icons.pause : Icons.play_arrow,
                            ),
                            label: Text(_isRunning ? 'إيقاف مؤقت' : 'بدء'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        IconButton.filledTonal(
                          onPressed: _resetTimer,
                          tooltip: 'إعادة ضبط',
                          icon: const Icon(Icons.restart_alt),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'اختر المدة اليومية',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [30, 60, 90, 120, 180].map((minutes) {
                final selected = _selectedMinutes == minutes;
                final label = minutes < 60
                    ? '$minutes دقيقة'
                    : minutes == 60
                        ? 'ساعة'
                        : '${minutes ~/ 60} ساعة${minutes % 60 == 30 ? ' ونصف' : ''}';
                return ChoiceChip(
                  label: Text(label),
                  selected: selected,
                  onSelected: (_) => _setDailyMinutes(minutes),
                );
              }).toList(),
            ),
            const SizedBox(height: 28),
            const Card(
              child: ListTile(
                leading: Icon(Icons.notifications_active_outlined),
                title: Text('تنبيه قبل انتهاء الوقت'),
                subtitle: Text('سيظهر تنبيه واضح عندما يتبقى 5 دقائق.'),
              ),
            ),
            const Card(
              child: ListTile(
                leading: Icon(Icons.shield_outlined),
                title: Text('الحماية المتقدمة'),
                subtitle: Text(
                  'سيتم ربط القفل وصلاحيات إدارة الجهاز في المرحلة التالية.',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
