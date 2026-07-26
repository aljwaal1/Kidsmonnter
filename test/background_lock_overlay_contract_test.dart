import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يحافظ القفل التلقائي على أوامر ولي الأمر والتنظيف الآمن', () {
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
    expect(service, contains('if (screenOn && isTimeFinished()) showLock() else dismissLockOverlay()'));
    expect(service, contains('releaseDeviceOwnerPolicies()'));
    expect(service, contains('stopSelf()'));
  });
}
