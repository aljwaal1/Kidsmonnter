import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('منع الحذف القوي يعتمد على Device Owner دون Accessibility', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(native, contains('PARENT_PIN_UNINSTALL_PROTECTION_MARKER'));
    expect(native, contains('setUninstallBlocked'));
    expect(native, contains('UNINSTALL_AUTHORIZED_BY_PARENT_PIN'));
    expect(native, contains('verifyPin(prefs, pin)'));
    expect(native, isNot(contains('missing.add("uninstall_guard")')));

    expect(flutter, contains('Device Owner'));
    expect(flutter, contains('منع الحذف النظامي'));
    expect(flutter, isNot(contains('قفل الحذف برمز الأب')));
    expect(flutter, isNot(contains("openAccessibilitySettings")));

    expect(manifest, isNot(contains('android.permission.BIND_ACCESSIBILITY_SERVICE')));
    expect(manifest, isNot(contains('UninstallGuardAccessibilityService')));
    expect(manifest, contains('KidsMonnterDeviceAdminReceiver'));
  });
}
