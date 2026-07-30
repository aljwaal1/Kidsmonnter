import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يطلب رمز الأب قبل الإيقاف الإجباري ولا يعترض تطبيقات أخرى', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();
    final accessibility =
        File('native/res/xml/uninstall_guard_accessibility.xml')
            .readAsStringSync();

    expect(native, contains('PARENT_PIN_FORCE_STOP_GUARD_MARKER'));
    expect(native, contains('class ForceStopPinActivity : Activity()'));
    expect(native, contains('APP_SETTINGS_AUTHORIZED_BY_PARENT_PIN'));
    expect(native, contains('FORCE_STOP_OR_APP_SETTINGS_INTERCEPTED'));
    expect(native, contains('Settings.ACTION_APPLICATION_DETAILS_SETTINGS'));
    expect(native, contains('SETTINGS_AUTH_WINDOW_MS = 90_000L'));
    expect(native, contains('lockPinBlockRemainingMs(prefs)'));
    expect(native, contains('registerLockPinFailure'));

    // لا يكفي اسم شاشة الإعدادات العام؛ يجب أن تذكر الصفحة KidsMonnter نفسه.
    expect(native, contains('if (!mentionsThisApp) return'));
    expect(native, contains('textMentionsKidsMonnter'));
    expect(native, contains('collectVisibleText(rootInActiveWindow)'));

    expect(manifest, contains('android:name=".ForceStopPinActivity"'));
    expect(accessibility, contains('typeViewClicked'));
  });
}
