import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Device Owner uninstall protection is mandatory', () {
    final flutter = File('lib/main.dart').readAsStringSync();
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(flutter, contains('MANDATORY_DEVICE_OWNER_SETUP_MARKER'));
    expect(flutter, contains('_devicePolicy.uninstallProtectionActive'));
    expect(flutter, contains('منع حذف التطبيق'));
    expect(flutter, contains('بدونها يمكن حذف التطبيق وإلغاء الحماية بالكامل'));

    expect(native, contains('MANDATORY_DEVICE_OWNER_SETUP_MARKER'));
    expect(native, contains('isDeviceOwnerApp(packageName)'));
    expect(native, contains('isUninstallBlocked(admin, packageName)'));
    expect(native, contains('device_owner_uninstall_block'));
  });
}
