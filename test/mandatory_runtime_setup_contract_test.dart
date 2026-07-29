import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('runtime permissions are mandatory before protection starts', () {
    final flutter = File('lib/main.dart').readAsStringSync();
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(flutter, contains('MANDATORY_RUNTIME_SETUP_MARKER'));
    expect(flutter, contains('إعداد الحماية الإجباري'));
    expect(flutter, contains('لا يمكن استخدام التطبيق قبل إكمال صلاحيات الحماية'));
    expect(flutter, contains('_runtimeSetupReady'));
    expect(flutter, contains("openOverlaySettings"));
    expect(flutter, contains("openBatteryOptimizationSettings"));
    expect(flutter, contains("openExactAlarmSettings"));

    expect(native, contains('MANDATORY_RUNTIME_SETUP_MARKER'));
    expect(native, contains('PROTECTION_START_BLOCKED'));
    expect(native, contains('MISSING_RUNTIME_REQUIREMENTS'));
    expect(native, contains('Settings.canDrawOverlays(this)'));
    expect(native, contains('isIgnoringBatteryOptimizations()'));
    expect(native, contains('canUseExactWatchdog()'));
  });
}
