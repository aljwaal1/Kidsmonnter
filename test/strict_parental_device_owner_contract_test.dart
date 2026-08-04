import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('الوضع الأبوي الصارم يتطلب Device Owner ويستخدم Lock Task', () {
    final strictPatch = File('tools/strict_parental_mode.py').readAsStringSync();
    final buildPatch =
        File('tools/play_protect_compatible.py').readAsStringSync();

    expect(buildPatch, contains('strict_parental_mode.py'));
    expect(strictPatch, contains('missing.add("device_owner")'));
    expect(strictPatch, contains('setStrictLockUi(true)'));
    expect(strictPatch, contains('setStrictLockUi(false)'));
    expect(strictPatch, contains('setLockTaskPackages'));
    expect(strictPatch, contains('setStatusBarDisabled'));
    expect(strictPatch, contains('setUninstallBlocked'));
    expect(strictPatch, contains('strictReady'));
    expect(strictPatch, contains('DEVICE_OWNER_REQUIRED'));
    expect(strictPatch, contains('STRICT_PARENTAL_DEVICE_OWNER_V1'));
    expect(strictPatch, contains('STRICT_PARENTAL_DEVICE_OWNER_UI_V1'));
  });
}
