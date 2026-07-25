import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('lock screen uses an internal keypad and does not keep or wake the display', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();
    final lockStart = source.indexOf('class LockActivity : Activity()');
    final lockEnd = source.indexOf('class KidsMonnterDeviceAdminReceiver');
    expect(lockStart, greaterThanOrEqualTo(0));
    expect(lockEnd, greaterThan(lockStart));
    final lockSource = source.substring(lockStart, lockEnd);

    expect(lockSource, contains('GridLayout(this)'));
    expect(lockSource, contains('enteredPin'));
    expect(lockSource, contains('refreshPinUi()'));
    expect(lockSource, contains('unlockWithPin(addTime = true)'));
    expect(lockSource, contains('unlockWithPin(addTime = false)'));
    expect(lockSource, contains('ScrollView(this)'));
    expect(lockSource, contains('.commit()'));
    expect(lockSource, contains('FLAG_SHOW_WHEN_LOCKED'));
    expect(lockSource, isNot(contains('EditText(this)')));
    expect(lockSource, isNot(contains('FLAG_KEEP_SCREEN_ON')));
    expect(lockSource, isNot(contains('FLAG_TURN_SCREEN_ON')));
    expect(lockSource, isNot(contains('FLAG_DISMISS_KEYGUARD')));
  });
}
