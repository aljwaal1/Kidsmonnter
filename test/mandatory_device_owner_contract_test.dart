import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('مسؤول الجهاز شرط إلزامي بينما Device Owner اختياري', () {
    final flutter = File('lib/main.dart').readAsStringSync();
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(flutter, contains('MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'));
    expect(flutter, contains('_devicePolicy.adminActive'));
    expect(flutter, contains('تفعيل مسؤول الجهاز'));
    expect(flutter, contains('activateDeviceAdministrator'));
    expect(flutter, isNot(contains('إعادة ضبط المصنع')));

    expect(native, contains('MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'));
    expect(native, contains('DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN'));
    expect(native, contains('dpm.isAdminActive(admin)'));
    expect(native, contains('device_admin_required'));
    expect(native, isNot(contains('device_owner_uninstall_block')));
  });
}
