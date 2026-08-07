import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Guard Mode يعلن Accessibility ويحمي صفحات الحذف والإيقاف برمز الأب', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(manifest, contains('BIND_ACCESSIBILITY_SERVICE'));
    expect(manifest, contains('UninstallGuardAccessibilityService'));
    expect(manifest, contains('ForceStopPinActivity'));
    expect(manifest, contains('UninstallPinActivity'));
    expect(manifest, contains('KidsMonnterDeviceAdminReceiver'));
    expect(manifest, contains('MonitorService'));
    expect(manifest, contains('SYSTEM_ALERT_WINDOW'));

    expect(native, contains('FORCE_STOP_OR_APP_SETTINGS_INTERCEPTED'));
    expect(native, contains('UNINSTALL_ATTEMPT_INTERCEPTED'));
    expect(native, contains('missing.add("uninstall_guard")'));
    expect(native, contains('configureDeviceOwnerPolicies'));
    expect(native, contains('setUninstallBlocked'));
    expect(native, contains('startLockTask'));
  });
}
