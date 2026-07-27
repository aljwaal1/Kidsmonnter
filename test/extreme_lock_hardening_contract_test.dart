import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يبني قفلاً مزدوجاً مع صمام أمان ومنع تجاوزات النظام', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(native, contains('EXTREME_LOCK_HARDENING_MARKER'));
    expect(native, contains('LOCK_TASK_FEATURE_NONE'));
    expect(native, contains('launchLockActivityIfDeviceOwner()'));
    expect(native, contains('LOCK_ACTIVITY_REASSERTED'));
    expect(native, contains('FLAG_SECURE'));
    expect(native, contains('FLAG_ALT_FOCUSABLE_IM'));
    expect(native, contains('systemGestureExclusionRects'));
    expect(native, contains('dispatchKeyEvent(event: KeyEvent)'));
    expect(native, contains('onWindowFocusChanged(hasFocus: Boolean)'));
    expect(native, contains('onUserLeaveHint()'));
    expect(native, contains('scheduleLockReassert()'));
    expect(native, contains('LOCK_ACTION_GRACE_MS'));
    expect(native, contains('lockActionInProgress'));
    expect(native, contains('PIN_FAILURE_STREAK_KEY'));
    expect(native, contains('registerLockPinFailure'));
    expect(native, contains('LOCK_FAIL_OPEN'));
    expect(native, contains('missing_or_corrupt_parent_pin'));
    expect(native, contains('clearLockPinFailureState'));

    final dismissStart = native.indexOf('private fun dismissLockOverlay()');
    final dismissEnd = native.indexOf('private fun monitorOverlayPermission()', dismissStart);
    final dismiss = native.substring(dismissStart, dismissEnd);
    expect(
      dismiss.indexOf('lockOverlayView = null'),
      lessThan(dismiss.indexOf('.removeViewImmediate(view)')),
    );

    expect(manifest, contains('android:supportsPictureInPicture="false"'));
    expect(manifest, contains('android:windowSoftInputMode="stateAlwaysHidden"'));
    expect(native, isNot(contains('FLAG_DISMISS_KEYGUARD')));
    expect(native, isNot(contains('FLAG_TURN_SCREEN_ON')));
  });
}
