import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يحمي مهلة محاولات إظهار شاشة القفل من التكرار كل ثانية', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(native, contains('LOCK_LAUNCH_COOLDOWN_MS = 5_000L'));
    expect(native, contains('lastLockLaunchElapsedMs'));
    expect(native, contains('SystemClock.elapsedRealtime()'));
    expect(
      native,
      contains(
        'if (now - lastLockLaunchElapsedMs < LOCK_LAUNCH_COOLDOWN_MS) return',
      ),
    );
    expect(native, contains('lastLockLaunchElapsedMs = now'));
    expect(native, contains('startActivity(Intent(this, LockActivity::class.java)'));
  });
}
