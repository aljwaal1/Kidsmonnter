from pathlib import Path

NATIVE = Path('native/MainActivityV2.kt')
FLUTTER = Path('lib/main.dart')
MARKER = 'DAILY_FAILED_ATTEMPT_REPORTS_MARKER'

native = NATIVE.read_text(encoding='utf-8')
flutter = FLUTTER.read_text(encoding='utf-8')

if MARKER in native and MARKER in flutter:
    print('Daily failed-attempt reports already merged')
    raise SystemExit(0)

native = native.replace(
    'private const val MAX_FAILED_ATTEMPTS = 50',
    'private const val MAX_FAILED_ATTEMPTS = 1000\n// DAILY_FAILED_ATTEMPT_REPORTS_MARKER: الاحتفاظ بسجل يومي موسع داخل الجهاز',
    1,
)

old_read = '''private fun readFailedAttempts(prefs: SharedPreferences): List<Map<String, String>> =
    prefs.getString(FAILED_ATTEMPTS_KEY, "").orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .mapNotNull { line ->
            val parts = line.split("|", limit = 2)
            if (parts.size == 2) mapOf("time" to parts[0], "source" to parts[1]) else null
        }
        .toList()
        .asReversed()
'''
new_read = '''private fun readFailedAttempts(prefs: SharedPreferences): List<Map<String, String>> =
    prefs.getString(FAILED_ATTEMPTS_KEY, "").orEmpty()
        .lineSequence()
        .filter { it.isNotBlank() }
        .mapNotNull { line ->
            val parts = line.split("|", limit = 2)
            if (parts.size != 2) return@mapNotNull null
            val timestamp = parts[0]
            val date = timestamp.substringBefore(' ', timestamp)
            val clock = timestamp.substringAfter(' ', timestamp)
            mapOf(
                "time" to timestamp,
                "date" to date,
                "clock" to clock,
                "source" to parts[1],
            )
        }
        .toList()
        .asReversed()
'''
if old_read not in native:
    raise SystemExit('تعذر العثور على دالة قراءة المحاولات')
native = native.replace(old_read, new_read, 1)

old_ui_start = "  Future<void> _showFailedAttempts() async {\n"
old_ui_end = "\n  // RUNTIME_DIAGNOSTICS_UI_MARKER"
start = flutter.find(old_ui_start)
end = flutter.find(old_ui_end, start)
if start < 0 or end < 0:
    raise SystemExit('تعذر العثور على واجهة المحاولات الفاشلة')

new_ui = r'''  // DAILY_FAILED_ATTEMPT_REPORTS_MARKER
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
                        title: Text(entry.key, textDirection: TextDirection.ltr),
                        subtitle: Text('${dayAttempts.length} محاولة خاطئة'),
                        children: dayAttempts
                            .map(
                              (attempt) => ListTile(
                                dense: true,
                                leading: const Icon(Icons.warning_amber_rounded),
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
'''
flutter = flutter[:start] + new_ui + flutter[end:]

flutter = flutter.replace(
    "title: const Text('المحاولات الفاشلة'),\n                subtitle: Text('عدد المحاولات: ${status.failedAttempts}'),",
    "title: const Text('تقارير المحاولات الخاطئة'),\n                subtitle: Text('محفوظة يوميًا — المجموع: ${status.failedAttempts}'),",
    1,
)

NATIVE.write_text(native, encoding='utf-8')
FLUTTER.write_text(flutter, encoding='utf-8')
print('Daily failed-attempt reports merged')
