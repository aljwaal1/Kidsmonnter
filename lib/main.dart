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
        colorSchemeSeed: const Color(0xFF436B62),
        scaffoldBackgroundColor: const Color(0xFFF4F7F5),
        cardTheme: const CardThemeData(
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(22)),
          ),
        ),
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
  static const _protectionEnabledKey = 'protection_enabled';
  static const _savedDateKey = 'saved_date';
  static const _lastUpdateKey = 'last_update';
  static const _fiveMinuteWarningKey = 'five_minute_warning';
  static const _oneMinuteWarningKey = 'one_minute_warning';

  int _selectedMinutes = 60;
  int _remainingSeconds = 3600;
  bool _protectionEnabled = false;
  bool _fiveMinuteWarningShown = false;
  bool _oneMinuteWarningShown = false;
  bool _loading = true;
  bool _finishDialogVisible = false;
  Timer? _timer;
  int _secondsSinceSave = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _restore();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _save();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.detached) {
      _save();
    } else if (state == AppLifecycleState.resumed) {
      _restoreElapsedTime();
    }
  }

  String _dateKey(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();
    final selected = prefs.getInt(_selectedMinutesKey) ?? 60;
    var remaining = prefs.getInt(_remainingSecondsKey) ?? selected * 60;
    var enabled = prefs.getBool(_protectionEnabledKey) ?? false;
    var fiveShown = prefs.getBool(_fiveMinuteWarningKey) ?? false;
    var oneShown = prefs.getBool(_oneMinuteWarningKey) ?? false;

    if (prefs.getString(_savedDateKey) != _dateKey(now)) {
      remaining = selected * 60;
      fiveShown = false;
      oneShown = false;
    } else if (enabled && remaining > 0) {
      final lastMillis = prefs.getInt(_lastUpdateKey);
      if (lastMillis != null) {
        final elapsed = now
            .difference(DateTime.fromMillisecondsSinceEpoch(lastMillis))
            .inSeconds;
        remaining = (remaining - elapsed).clamp(0, selected * 60).toInt();
      }
    }

    if (remaining == 0) enabled = true;
    if (!mounted) return;
    setState(() {
      _selectedMinutes = selected;
      _remainingSeconds = remaining;
      _protectionEnabled = enabled;
      _fiveMinuteWarningShown = fiveShown || remaining <= 300;
      _oneMinuteWarningShown = oneShown || remaining <= 60;
      _loading = false;
    });

    if (_protectionEnabled && _remainingSeconds > 0) _startTimer();
    await _save();
    if (_remainingSeconds == 0) _showFinishedDialog();
  }

  Future<void> _restoreElapsedTime() async {
    if (_loading || !_protectionEnabled || _remainingSeconds == 0) return;
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();

    if (prefs.getString(_savedDateKey) != _dateKey(now)) {
      _timer?.cancel();
      setState(() {
        _remainingSeconds = _selectedMinutes * 60;
        _fiveMinuteWarningShown = false;
        _oneMinuteWarningShown = false;
      });
      _startTimer();
      await _save();
      return;
    }

    final lastMillis = prefs.getInt(_lastUpdateKey);
    if (lastMillis == null) return;
    final elapsed = now
        .difference(DateTime.fromMillisecondsSinceEpoch(lastMillis))
        .inSeconds;
    if (elapsed <= 0) return;

    setState(() {
      _remainingSeconds = (_remainingSeconds - elapsed)
          .clamp(0, _selectedMinutes * 60)
          .toInt();
    });
    _checkWarnings();
    if (_remainingSeconds == 0) {
      _timer?.cancel();
      await _save();
      _showFinishedDialog();
    } else {
      _startTimer();
      await _save();
    }
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();
    await prefs.setInt(_selectedMinutesKey, _selectedMinutes);
    await prefs.setInt(_remainingSecondsKey, _remainingSeconds);
    await prefs.setBool(_protectionEnabledKey, _protectionEnabled);
    await prefs.setString(_savedDateKey, _dateKey(now));
    await prefs.setInt(_lastUpdateKey, now.millisecondsSinceEpoch);
    await prefs.setBool(_fiveMinuteWarningKey, _fiveMinuteWarningShown);
    await prefs.setBool(_oneMinuteWarningKey, _oneMinuteWarningShown);
  }

  void _startTimer() {
    _timer?.cancel();
    if (!_protectionEnabled || _remainingSeconds <= 0) return;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) async {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_remainingSeconds <= 1) {
        timer.cancel();
        setState(() => _remainingSeconds = 0);
        await _save();
        _showFinishedDialog();
        return;
      }
      setState(() => _remainingSeconds--);
      _checkWarnings();
      _secondsSinceSave++;
      if (_secondsSinceSave >= 10) {
        _secondsSinceSave = 0;
        await _save();
      }
    });
  }

  void _checkWarnings() {
    if (_remainingSeconds <= 300 && !_fiveMinuteWarningShown) {
      _fiveMinuteWarningShown = true;
      _showWarning('تبقّى 5 دقائق', 'احفظ ما تعمل عليه قبل انتهاء الوقت.');
      _save();
    }
    if (_remainingSeconds <= 60 && !_oneMinuteWarningShown) {
      _oneMinuteWarningShown = true;
      _showWarning('تبقّت دقيقة واحدة', 'سينتهي وقت الهاتف بعد دقيقة.');
      _save();
    }
  }

  void _showWarning(String title, String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          duration: const Duration(seconds: 8),
          behavior: SnackBarBehavior.floating,
          content: Row(
            children: [
              const Icon(Icons.timer_outlined, color: Colors.white),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
                    Text(message),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
  }

  Future<void> _toggleProtection(bool enabled) async {
    setState(() => _protectionEnabled = enabled);
    if (enabled) {
      _startTimer();
    } else {
      _timer?.cancel();
    }
    await _save();
  }

  Future<void> _requestDurationChange(int minutes) async {
    if (minutes == _selectedMinutes) return;
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('تغيير المدة اليومية'),
        content: Text(
          'سيتم اعتماد ${_durationLabel(minutes)} وإعادة رصيد اليوم من البداية.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('اعتماد'),
          ),
        ],
      ),
    );
    if (approved != true || !mounted) return;

    _timer?.cancel();
    setState(() {
      _selectedMinutes = minutes;
      _remainingSeconds = minutes * 60;
      _fiveMinuteWarningShown = false;
      _oneMinuteWarningShown = false;
    });
    if (_protectionEnabled) _startTimer();
    await _save();
  }

  Future<void> _showFinishedDialog() async {
    if (!mounted || _finishDialogVisible) return;
    _finishDialogVisible = true;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => PopScope(
        canPop: false,
        child: AlertDialog(
          icon: const Icon(Icons.lock_clock_outlined, size: 48),
          title: const Text('انتهى وقت الهاتف'),
          content: const Text(
            'تم استهلاك الوقت المتاح لهذا اليوم. فتح الهاتف يحتاج إلى موافقة ولي الأمر.',
            textAlign: TextAlign.center,
          ),
          actionsAlignment: MainAxisAlignment.center,
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('طلب موافقة ولي الأمر'),
            ),
          ],
        ),
      ),
    );
    _finishDialogVisible = false;
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
    if (minutes == 60) return 'ساعة واحدة';
    if (minutes == 90) return 'ساعة ونصف';
    if (minutes == 120) return 'ساعتان';
    return '${minutes ~/ 60} ساعات';
  }

  double get _progress {
    final total = _selectedMinutes * 60;
    if (total == 0) return 0;
    return (_remainingSeconds / total).clamp(0, 1).toDouble();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('حارس وقت الأطفال'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: scheme.primary,
                    child: Icon(Icons.shield_outlined, color: scheme.onPrimary),
                  ),
                  const SizedBox(width: 14),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'رصيد واحد للهاتف بالكامل',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        SizedBox(height: 4),
                        Text('جميع التطبيقات تُخصم من الوقت اليومي نفسه.'),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'الحماية اليومية',
                          style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                        ),
                        Switch(
                          value: _protectionEnabled,
                          onChanged: _remainingSeconds == 0 ? null : _toggleProtection,
                        ),
                      ],
                    ),
                    const Divider(height: 28),
                    const Text('الوقت المتبقي اليوم'),
                    const SizedBox(height: 10),
                    Text(
                      _formattedRemaining,
                      textDirection: TextDirection.ltr,
                      style: const TextStyle(
                        fontSize: 44,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 16),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: LinearProgressIndicator(
                        value: _progress,
                        minHeight: 12,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          _protectionEnabled ? Icons.check_circle : Icons.pause_circle,
                          size: 18,
                          color: _protectionEnabled ? Colors.green.shade700 : Colors.grey,
                        ),
                        const SizedBox(width: 7),
                        Text(
                          _remainingSeconds == 0
                              ? 'انتهى وقت اليوم'
                              : _protectionEnabled
                                  ? 'الحماية مفعّلة والعداد يعمل تلقائيًا'
                                  : 'الحماية متوقفة مؤقتًا',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
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
              spacing: 9,
              runSpacing: 9,
              children: [30, 60, 90, 120, 180].map((minutes) {
                return ChoiceChip(
                  label: Text(_durationLabel(minutes)),
                  selected: _selectedMinutes == minutes,
                  onSelected: (_) => _requestDurationChange(minutes),
                );
              }).toList(),
            ),
            const SizedBox(height: 22),
            const Card(
              child: Column(
                children: [
                  ListTile(
                    leading: Icon(Icons.notifications_active_outlined),
                    title: Text('تنبيهات انتهاء الوقت'),
                    subtitle: Text('تنبيه عند بقاء 5 دقائق، وتنبيه أخير عند بقاء دقيقة.'),
                  ),
                  Divider(height: 1),
                  ListTile(
                    leading: Icon(Icons.save_outlined),
                    title: Text('حفظ تلقائي'),
                    subtitle: Text('المدة والوقت المتبقي محفوظان بعد إغلاق التطبيق.'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
