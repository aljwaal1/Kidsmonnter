import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Guard Mode يحمي الحذف برمز الأب وAccessibility مع Device Owner اختياري', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(native, contains('PARENT_PIN_UNINSTALL_PROTECTION_MARKER'));
    expect(native, contains('setUninstallBlocked'));
    expect(native, contains('UNINSTALL_AUTHORIZED_BY_PARENT_PIN'));
    expect(native, contains('verifyPin(prefs, pin)'));
    expect(native, contains('missing.add("uninstall_guard")'));
    expect(native, contains('UNINSTALL_ATTEMPT_INTERCEPTED'));

    expect(flutter, contains('قفل الحذف برمز الأب'));
    expect(flutter, contains("openAccessibilitySettings"));
    expect(flutter, contains('_uninstallGuardEnabled'));

    expect(manifest, contains('android.permission.BIND_ACCESSIBILITY_SERVICE'));
    expect(manifest, contains('UninstallGuardAccessibilityService'));
    expect(manifest, contains('KidsMonnterDeviceAdminReceiver'));
  });
}
