import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('foreground notification opens the parent dashboard safely', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();

    expect(native, contains('guardNotificationContentIntent'));
    expect(native, contains('PendingIntent.getActivity'));
    expect(native, contains('Intent(this, MainActivity::class.java)'));
    expect(native, contains('Intent.FLAG_ACTIVITY_CLEAR_TOP'));
    expect(native, contains('Intent.FLAG_ACTIVITY_SINGLE_TOP'));
    expect(native, contains('PendingIntent.FLAG_IMMUTABLE'));
    expect(
      native,
      contains('.setContentIntent(guardNotificationContentIntent())'),
    );
  });
}
