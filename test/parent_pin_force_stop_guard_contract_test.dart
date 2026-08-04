import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('النسخة العادية لا تعلن Accessibility وتحافظ على الحماية المدارة', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(manifest, isNot(contains('BIND_ACCESSIBILITY_SERVICE')));
    expect(manifest, isNot(contains('UninstallGuardAccessibilityService')));
    expect(manifest, contains('KidsMonnterDeviceAdminReceiver'));
    expect(manifest, contains('MonitorService'));
    expect(manifest, contains('SYSTEM_ALERT_WINDOW'));

    expect(native, contains('configureDeviceOwnerPolicies'));
    expect(native, contains('setUninstallBlocked'));
    expect(native, contains('startLockTask'));
    expect(native, isNot(contains('missing.add("uninstall_guard")')));
  });
}
