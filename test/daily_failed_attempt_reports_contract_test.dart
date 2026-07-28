import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يحفظ ويعرض المحاولات الخاطئة كتقارير يومية', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();

    expect(native, contains('DAILY_FAILED_ATTEMPT_REPORTS_MARKER'));
    expect(native, contains('MAX_FAILED_ATTEMPTS = 1000'));
    expect(native, contains('"date" to date'));
    expect(native, contains('"clock" to clock'));
    expect(native, contains('entries.takeLast(MAX_FAILED_ATTEMPTS)'));

    expect(flutter, contains('DAILY_FAILED_ATTEMPT_REPORTS_MARKER'));
    expect(flutter, contains('التقارير اليومية للمحاولات الخاطئة'));
    expect(flutter, contains('grouped.putIfAbsent'));
    expect(flutter, contains('ExpansionTile'));
    expect(flutter, contains('محاولة خاطئة'));
    expect(flutter, isNot(contains("label: const Text('إرسال التقرير')")));
  });
}
