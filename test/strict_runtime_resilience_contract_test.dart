import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يحمي تشغيل الخلفية والإقلاع بمسارات استعادة متعددة', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();
    final dart = File('lib/main.dart').readAsStringSync();

    expect(native, contains('STRICT_RUNTIME_RESILIENCE_MARKER'));
    expect(native, contains('createDeviceProtectedStorageContext()'));
    expect(native, contains('setExactAndAllowWhileIdle'));
    expect(native, contains('scheduleBootRetries()'));
    expect(native, contains('BOOT_RETRIES_SCHEDULED'));
    expect(native, contains('PowerManager.PARTIAL_WAKE_LOCK'));
    expect(native, contains('BOOT_SERVICE_START_FAILED'));
    expect(native, contains('syncBootProtectionState(true)'));
    expect(native, contains('syncBootProtectionState(false)'));
    expect(native, contains('openExactAlarmSettings'));
    expect(native, contains('openBatteryOptimizationSettings'));

    final serviceStart = native.indexOf('override fun onCreate() {',
        native.indexOf('class MonitorService'));
    final serviceCreate = native.substring(serviceStart, serviceStart + 700);
    expect(
      serviceCreate.indexOf('startForeground('),
      lessThan(serviceCreate.indexOf('appendGuardLog("SERVICE_CREATED"')),
    );

    expect(manifest, contains('android.permission.SCHEDULE_EXACT_ALARM'));
    expect(
      manifest,
      contains('android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS'),
    );
    expect(manifest, contains('android:directBootAware="true"'));
    expect(manifest, contains('com.explapp.kidstimeguard.BOOT_RETRY'));

    expect(dart, contains('STRICT_RUNTIME_UI_MARKER'));
    expect(dart, contains('تفعيل المنبه الدقيق'));
    expect(dart, contains('استثناء البطارية'));
  });
}
