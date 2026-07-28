import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('إيقاف حماية الوقت يحرر القفل لكنه يبقي منع حذف التطبيق', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();

    expect(source, contains('private fun Context.releaseDeviceOwnerPolicies()'));
    expect(source, contains('manager.setStatusBarDisabled(admin, false)'));
    expect(source, contains('manager.setLockTaskPackages(admin, emptyArray<String>())'));

    final releaseStart =
        source.indexOf('private fun Context.releaseDeviceOwnerPolicies()');
    final releaseEnd = source.indexOf(
      'private fun Activity.openSelfUninstallScreen()',
      releaseStart,
    );
    expect(releaseStart, greaterThanOrEqualTo(0));
    expect(releaseEnd, greaterThan(releaseStart));
    final releaseBlock = source.substring(releaseStart, releaseEnd);
    expect(
      releaseBlock,
      contains('manager.setUninstallBlocked(admin, packageName, true)'),
    );
    expect(
      releaseBlock,
      isNot(contains('manager.setUninstallBlocked(admin, packageName, false)')),
    );

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
