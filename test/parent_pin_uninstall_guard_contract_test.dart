import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('لا يسمح بالحذف إلا بعد رمز الأب', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(native, contains('PARENT_PIN_UNINSTALL_GUARD_MARKER'));
    expect(native, contains('UninstallGuardAccessibilityService'));
    expect(native, contains('UninstallPinActivity'));
    expect(native, contains('UNINSTALL_ATTEMPT_INTERCEPTED'));
    expect(native, contains('verifyPin(prefs, candidate)'));
    expect(native, contains('UNINSTALL_AUTHORIZED_UNTIL_KEY'));
    expect(native, contains('manager.removeActiveAdmin(admin)'));
    expect(native, contains('isUninstallGuardAccessibilityEnabled()'));

    expect(flutter, contains('PARENT_PIN_UNINSTALL_GUARD_MARKER'));
    expect(flutter, contains('_uninstallGuardEnabled'));
    expect(flutter, contains('قفل الحذف برمز الأب'));
    expect(flutter, contains("openAccessibilitySettings"));

    expect(manifest, contains('PARENT_PIN_UNINSTALL_GUARD_MARKER'));
    expect(manifest, contains('android.permission.BIND_ACCESSIBILITY_SERVICE'));
    expect(manifest, contains('@xml/uninstall_guard_accessibility'));
  });
}
