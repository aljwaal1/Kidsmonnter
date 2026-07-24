import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('getStatus يستعيد خدمة الحماية عند قدم النبضة دون تغيير الإعدادات', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();

    expect(source, contains('private fun shouldRecoverProtectionService'));
    expect(source, contains('age > 30_000L || age < -5_000L'));
    expect(
      source,
      contains(
        'if (shouldRecoverProtectionService(prefs)) startMonitorServiceSafely()',
      ),
    );
    expect(
      source,
      isNot(contains('if (shouldRecoverProtectionService(prefs)) startProtection')),
    );
  });
}
