import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('lock screen offers a PIN-protected emergency protection stop', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();
    final lockStart = source.indexOf('class LockActivity : Activity()');
    final lockEnd = source.indexOf('class KidsMonnterDeviceAdminReceiver');
    expect(lockStart, greaterThanOrEqualTo(0));
    expect(lockEnd, greaterThan(lockStart));

    final lockSource = source.substring(lockStart, lockEnd);
    expect(lockSource, contains('text = "إيقاف الحماية"'));
    expect(lockSource, contains('disableProtectionWithPin()'));
    expect(lockSource, contains('verifyPin(prefs, pin)'));
    expect(lockSource, contains('.putBoolean("enabled", false)'));
    expect(lockSource, contains('.remove(LAST_TICK_KEY)'));
    expect(lockSource, contains('.commit()'));
    expect(
      lockSource,
      contains('stopService(Intent(this, MonitorService::class.java))'),
    );
    expect(lockSource, contains('exitLock()'));
  });
}
