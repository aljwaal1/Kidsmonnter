import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('stopping protection releases device-owner restrictions', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();

    expect(source, contains('private fun Context.releaseDeviceOwnerPolicies()'));
    expect(source, contains('manager.setStatusBarDisabled(admin, false)'));
    expect(source, contains('manager.setUninstallBlocked(admin, packageName, false)'));
    expect(source, contains('manager.setLockTaskPackages(admin, emptyArray<String>())'));

    final mainStopStart = source.indexOf('"stopProtection" -> {');
    final mainStopEnd = source.indexOf('"addTime" -> {', mainStopStart);
    expect(mainStopStart, greaterThanOrEqualTo(0));
    expect(mainStopEnd, greaterThan(mainStopStart));
    expect(
      source.substring(mainStopStart, mainStopEnd),
      contains('releaseDeviceOwnerPolicies()'),
    );

    final lockStopStart = source.indexOf('private fun disableProtectionWithPin()');
    final lockStopEnd = source.indexOf(
      'private fun unlockWithPin(addTime: Boolean)',
      lockStopStart,
    );
    expect(lockStopStart, greaterThanOrEqualTo(0));
    expect(lockStopEnd, greaterThan(lockStopStart));
    expect(
      source.substring(lockStopStart, lockStopEnd),
      contains('releaseDeviceOwnerPolicies()'),
    );
  });
}
