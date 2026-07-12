import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

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

class _DailyTimeScreenState extends State<DailyTimeScreen>
    with WidgetsBindingObserver {
  static const _selectedMinutesKey = 'selected_minutes';
  static const _remainingSecondsKey = 'remaining_seconds';
  static const _isRunningKey = 'is_running';
  static const _savedDateKey = 'saved_date';
  static const _lastUpdateKey = 'last_update';
  static const _warningShownKey = 'five_minute_warning_shown';

  int _selectedMinutes = 60;
  int _remainingSeconds = 3600;
  Timer? _timer;
  bool _isRunning = false;
  bool _fiveMinuteWarningShown = false;
  bool _isLoading = true;
  int _secondsSinceLastSave = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _restoreState();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _saveState();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.detached) {
      _saveState();
    } else if (state == AppLifecycleState.resumed) {
      _refreshAfterReturn();
    }
  }

  String _dateKey(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  Future<void> _restoreState() async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();
    final today = _dateKey(now);
    final selected = prefs.getInt(_selectedMinutesKey) ?? 60;
    var remaining = prefs.getInt(_remainingSecondsKey) ?? selected * 60;
    var running = prefs.getBool(_isRunningKey) ?? false;
    var warned = prefs.getBool(_warningShownKey) ?? false;

    if (prefs.getString(_savedDateKey) != today) {
      remaining = selected * 60;
      running = false;
      warned = false;
    } else if (running) {
      final savedMillis = prefs.getInt(_lastUpdateKey);
      if (savedMillis != null) {
        final elapsed = now
            .difference(DateTime.fromMillisecondsSinceEpoch(savedMillis))
            .inSeconds;
        remaining = (remaining - elapsed).clamp(0, selected * 60).toInt();
      }
    }

    if (!mounted) return;
    setState(() {
      _selectedMinutes = selected;
      _remainingSeconds = remaining;
      _isRunning = running && remaining > 0;
      _fiveMinuteWarningShown = warned || remaining <= 300;
      _isLoading = false;
    });

    if (_isRunning) _startTicker();
    await _saveState();

    if (_remainingSeconds == 0) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _showTimeFinishedDialog();
      });
    }
  }

  Future<void> _refreshAfterReturn() async {
    if (_isLoading) return;
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();

    if (prefs.getString(_savedDateKey) != _dateKey(now)) {
      _timer?.cancel();
      setState(() {
        _remainingSeconds = _selectedMinutes * 60;
        _isRunning = false;
        _fiveMinuteWarningShown = false;
      });
      await _saveState();
      return;
    }

    if (!_isRunning) return;
    final savedMillis = prefs.getInt(_lastUpdateKey);
    if (savedMillis == null) return;

    final elapsed = now
        .difference(DateTime.fromMillisecondsSinceEpoch(savedMillis))
        .inSeconds;
    if (elapsed <= 0) return;

    final updated = (_remainingSeconds - elapsed)
        .clamp(0, _selectedMinutes * 60)
        .toInt();
    setState(() {
      _remainingSeconds = updated;
      if (updated == 0) _isRunning = false;
    });

    if (_remainingSeconds <= 300 && !_fiveMinuteWarningShown) {
      _showFiveMinuteWarning();
    }

    if (_remainingSeconds == 0) {
      _timer?.cancel();
      await _saveState();
      await _showTimeFinishedDialog();
    } else {
      _startTicker();
      await _saveState();
    }
  }

  Future<void> _saveState() async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();
    await prefs.setInt(_selectedMinutesKey, _selectedMinutes);
    await prefs.setInt(_remainingSecondsKey, _remainingSeconds);
    await prefs.setBool(_isRunningKey, _isRunning);
    await prefs.setString(_savedDateKey, _dateKey(now));
    await prefs.setInt(_lastUpdateKey, now.millisecondsSinceEpoch);
    await prefs.setBool(_warningShownKey, _fiveMinuteWarningShown);
  }

  Future<void> _setDailyMinutes(int minutes) async {
    _timer?.cancel();
    setState(() {
      _selectedMinutes = minutes;
      _remainingSeconds = minutes * 60;
      _isRunning = false;
      _fiveMinuteWarningShown = false;
    });
    await _saveState();
  }

  Future<void> _toggleTimer() async {
    if (_isRunning) {
      _timer?.cancel();
      setState(() => _isRunning = false);
    } else if (_remainingSeconds > 0) {
      setState(() => _isRunning = true);
      _startTicker();
    }
    await _saveState();
  }

  void _startTicker() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) async {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_remainingSeconds <= 1) {
        timer.cancel();
        setState(() {
          _remainingSeconds = 0;
          _isRunning = false;
        });
        await _saveState();
        await _showTimeFinishedDialog();
        return;
      }

      setState(() => _remainingSeconds--);
      _secondsSinceLastSave++;
      if (_remainingSeconds <= 300 && !_fiveMinuteWarningShown) {
        _showFiveMinuteWarning();
      }
      if (_secondsSinceLastSave >= 10) {
        _secondsSinceLastSave = 0;
        await _saveState();
      }
    });
  }

  void _showFiveMinuteWarning() {
    if (!mounted) return;
    setState(() => _fiveMinuteWarningShown = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        duration: Duration(seconds: 8),
        content: Text(
          'تبقّى 5 دقائق فقط من وقت استخدام الهاتف اليوم. احفظ ما تعمل عليه.',
          textAlign: TextAlign.center,
        ),
      ),
    );
    _saveState();
  }

  Future<void> _resetTimer() async {
    _timer?.cancel();
    setState(() {
      _remainingSeconds = _selectedMinutes * 60;
      _isRunning = false;
      _fiveMinuteWarningShown = false;
    });
    await _saveState();
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

  String _durationLabel(int minutes) {
    if (minutes < 60) return '$minutes دقيقة';
    if (minutes == 60) return 'ساعة';
    return '${minutes ~/ 60} ساعة${minutes % 60 == 30 ? ' ونصف' : ''}';
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

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
            const Text('جميع التطبيقات تُحسب من رصيد واحد للهاتف بالكامل.'),
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
                    const SizedBox(height: 8),
                    Text(
                      _isRunning ? 'العداد يعمل الآن' : 'العداد متوقف مؤقتًا',
                      style: TextStyle(
                        color: _isRunning ? Colors.green.shade700 : Colors.grey,
                        fontWeight: FontWeight.w600,
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
                return ChoiceChip(
                  label: Text(_durationLabel(minutes)),
                  selected: _selectedMinutes == minutes,
                  onSelected: (_) => _setDailyMinutes(minutes),
                );
              }).toList(),
            ),
            const SizedBox(height: 28),
            const Card(
              child: ListTile(
                leading: Icon(Icons.save_outlined),
                title: Text('حفظ تلقائي'),
                subtitle: Text(
                  'يُحفظ الوقت المتبقي ويُستعاد بعد إغلاق التطبيق أو إعادة تشغيل الهاتف.',
                ),
              ),
            ),
            const Card(
              child: ListTile(
                leading: Icon(Icons.today_outlined),
                title: Text('رصيد يومي جديد'),
                subtitle: Text('يُعاد ضبط الرصيد تلقائيًا عند بداية يوم جديد.'),
              ),
            ),
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
