import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('منع الحذف يعمل افتراضياً ولا يحتاج زر تطبيق سياسات', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final flutter = File('lib/main.dart').readAsStringSync();

    expect(native, contains('ensureUninstallProtection()'));
    expect(native, contains('setUninstallBlocked(deviceAdminComponent(), packageName, true)'));
    expect(native, contains('UNINSTALL_PROTECTION_ENFORCED'));

    expect(flutter, contains('DEFAULT_UNINSTALL_PROTECTION_UI_MARKER'));
    expect(flutter, contains('منع حذف التطبيق يعمل تلقائيًا'));
    expect(flutter, contains('لا يوجد زر تشغيل'));
    expect(flutter, contains('_authorizeUninstall'));
    expect(flutter, contains("label: const Text('حذف')"));
    expect(flutter, isNot(contains('_buildUninstallProtectionCard(status)')));
    expect(flutter, isNot(contains("label: Text(active ? 'تطبيق السياسات'")));
  });
}
