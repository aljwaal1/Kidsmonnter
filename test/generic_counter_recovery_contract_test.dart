import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يستعيد العداد الزمن بعد توقف الخدمة دون احتساب شاشة القفل', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(native, contains('GENERIC_COUNTER_RECOVERY_MARKER'));
    expect(native, contains('LAST_USAGE_ELIGIBLE_KEY'));
    expect(native, contains('recoverElapsedUsageIfNeeded("service_created")'));
    expect(native, contains('recoverElapsedUsageIfNeeded("service_start_command")'));
    expect(native, contains('COUNTER_RECOVERED'));
    expect(native, contains('COUNTER_ANCHOR_RESET_REASON'));
    expect(native, contains('SystemClock.elapsedRealtime()'));
    expect(native, contains('KeyguardManager'));
    expect(native, contains('!keyguard.isDeviceLocked'));
    expect(native, isNot(contains('coerceIn(0, 300)')));
  });
}
