import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('LockActivity must not wake the screen from the manifest', () {
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();

    expect(manifest, contains('android:name=".LockActivity"'));
    expect(manifest, contains('android:showWhenLocked="true"'));
    expect(manifest, isNot(contains('android:turnScreenOn="true"')));
  });
}
