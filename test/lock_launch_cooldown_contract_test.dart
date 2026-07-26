import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يعرض القفل من خدمة الخلفية دون تشغيل Activity محظورة', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final serviceStart = native.indexOf('class MonitorService');
    final serviceEnd = native.indexOf('class LockActivity');

    expect(serviceStart, greaterThanOrEqualTo(0));
    expect(serviceEnd, greaterThan(serviceStart));

    final service = native.substring(serviceStart, serviceEnd);
    expect(native, contains('LOCK_LAUNCH_COOLDOWN_MS = 5_000L'));
    expect(service, contains('lastLockLaunchElapsedMs'));
    expect(service, contains('SystemClock.elapsedRealtime()'));
    expect(
      service,
      contains(
        'if (now - lastLockLaunchElapsedMs < LOCK_LAUNCH_COOLDOWN_MS) return',
      ),
    );
    expect(service, contains('lastLockLaunchElapsedMs = now'));
    expect(service, contains('BACKGROUND_LOCK_OVERLAY_MARKER'));
    expect(
      service,
      contains('WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY'),
    );
    expect(service, contains('manager.addView(view, params)'));
    expect(
      service,
      isNot(contains('startActivity(Intent(this, LockActivity::class.java)')),
    );
  });
}
