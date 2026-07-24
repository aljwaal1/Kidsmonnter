import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('تطلب الحماية إذن الإشعارات على Android 13 وما بعده', () {
    final nativeSource = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(
      manifest,
      contains('android.permission.POST_NOTIFICATIONS'),
      reason: 'يجب أن يبقى إذن الإشعارات معلنًا في Manifest.',
    );
    expect(nativeSource, contains('requestNotificationPermissionIfNeeded'));
    expect(nativeSource, contains('Build.VERSION_CODES.TIRAMISU'));
    expect(nativeSource, contains('Manifest.permission.POST_NOTIFICATIONS'));
    expect(
      nativeSource,
      contains('requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7001)'),
    );

    final startProtectionIndex = nativeSource.indexOf('"startProtection" -> {');
    final restartServiceIndex = nativeSource.indexOf('"restartProtectionService" -> {');
    expect(startProtectionIndex, greaterThanOrEqualTo(0));
    expect(restartServiceIndex, greaterThan(startProtectionIndex));

    final startProtectionBlock = nativeSource.substring(
      startProtectionIndex,
      restartServiceIndex,
    );
    expect(startProtectionBlock, contains('requestNotificationPermissionIfNeeded()'));
    expect(startProtectionBlock, contains('startMonitorServiceSafely()'));
  });
}
