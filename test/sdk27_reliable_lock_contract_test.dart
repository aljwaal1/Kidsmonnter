import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يفتح شاشة القفل الكاملة على Android 8.1 دون اشتراط Device Owner', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(native, contains('SDK27_RELIABLE_LOCK_MARKER'));
    expect(native, contains('launchLockActivityReliably()'));
    expect(
      native,
      contains('Build.VERSION.SDK_INT <= Build.VERSION_CODES.P'),
    );
    expect(native, contains('LOCK_ACTIVITY_STARTED'));
    expect(native, contains('LOCK_ACTIVITY_START_FAILED'));
    expect(native, contains('LOCK_TRIGGERED'));
    expect(native, contains('LOCK_EVALUATION'));
    expect(native, isNot(contains('launchLockActivityIfDeviceOwner()')));
  });
}
