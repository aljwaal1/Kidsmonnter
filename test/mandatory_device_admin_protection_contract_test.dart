import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يفرض مسؤول الجهاز دون اشتراط إعادة ضبط المصنع', () {
    final flutter = File('lib/main.dart').readAsStringSync();
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(flutter, contains('MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'));
    expect(flutter, contains('_devicePolicy.adminActive'));
    expect(flutter, contains('تفعيل مسؤول الجهاز'));
    expect(flutter, contains("invokeMethod<void>('activateDeviceAdministrator')"));
    expect(flutter, isNot(contains('يلزم جهاز جديد أو إعادة ضبط المصنع')));

    expect(native, contains('MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER'));
    expect(native, contains('DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN'));
    expect(native, contains('DevicePolicyManager.EXTRA_DEVICE_ADMIN'));
    expect(native, contains('if (!dpm.isAdminActive(admin)) missing.add("device_admin")'));
  });
}
