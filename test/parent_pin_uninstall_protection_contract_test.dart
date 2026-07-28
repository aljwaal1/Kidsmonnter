import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('لا يسمح بحذف التطبيق إلا بعد رمز الأب في وضع Device Owner', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();

    expect(native, contains('PARENT_PIN_UNINSTALL_PROTECTION_MARKER'));
    expect(native, contains('ensureUninstallProtection()'));
    expect(native, contains('"authorizeUninstall"'));
    expect(native, contains('verifyPin(prefs, pin)'));
    expect(native, contains('UNINSTALL_PIN_REJECTED'));
    expect(native, contains('DEVICE_OWNER_REQUIRED'));
    expect(native, contains('UNINSTALL_AUTHORIZED_BY_PARENT_PIN'));
    expect(native, contains('setUninstallBlocked(admin, packageName, false)'));
    expect(native, contains('clearDeviceOwnerApp(packageName)'));
    expect(native, contains('Intent.ACTION_DELETE'));
    expect(native, contains('SYSTEM_UNINSTALL_SCREEN_OPENED'));

    final releaseStart =
        native.indexOf('private fun Context.releaseDeviceOwnerPolicies()');
    final releaseEnd = native.indexOf(
      'private fun Activity.openSelfUninstallScreen()',
      releaseStart,
    );
    final releaseBlock = native.substring(releaseStart, releaseEnd);
    expect(
      releaseBlock,
      contains('setUninstallBlocked(admin, packageName, true)'),
    );
    expect(
      releaseBlock,
      contains('RUNTIME_POLICIES_RELEASED_UNINSTALL_STILL_BLOCKED'),
    );
    expect(
      releaseBlock,
      isNot(contains('setUninstallBlocked(admin, packageName, false)')),
    );

    expect(flutter, contains('PARENT_PIN_UNINSTALL_UI_MARKER'));
    expect(flutter, contains("invokeMethod<void>('authorizeUninstall'"));
    expect(flutter, contains('أدخل رمز الأب للسماح بالحذف'));
    expect(flutter, contains('السماح بحذف التطبيق؟'));
    expect(flutter, contains('لن تعود الحماية الكاملة'));
  });
}
