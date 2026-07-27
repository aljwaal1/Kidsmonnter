import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يحافظ القفل التلقائي على النافذة ويفتح النشاط الكامل عند دعمه', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final serviceStart = native.indexOf('class MonitorService');
    final serviceEnd = native.indexOf('class LockActivity');

    expect(serviceStart, greaterThanOrEqualTo(0));
    expect(serviceEnd, greaterThan(serviceStart));

    final service = native.substring(serviceStart, serviceEnd);
    expect(service, contains('buildBackgroundLockOverlay()'));
    expect(service, contains('verifyBackgroundLockPin'));
    expect(service, contains('addTimeFromBackgroundLock()'));
    expect(service, contains('unlockTodayFromBackgroundLock()'));
    expect(service, contains('stopProtectionFromBackgroundLock()'));
    expect(service, contains('dismissLockOverlay()'));
    expect(service, contains('.removeViewImmediate(view)'));
    expect(service, contains('launchLockActivityReliably()'));
    expect(service, contains('Intent(this, LockActivity::class.java)'));
    expect(service, contains('FLAG_SECURE'));
    expect(service, contains('FLAG_ALT_FOCUSABLE_IM'));
    expect(service, contains('systemGestureExclusionRects'));
    expect(service, contains('LOCK_ACTIVITY_STARTED'));
    expect(service, contains('releaseDeviceOwnerPolicies()'));
    expect(service, contains('stopSelf()'));
    expect(
      service,
      isNot(contains(
          'if (screenOn && isTimeFinished()) showLock() else dismissLockOverlay()')),
    );
  });
}
