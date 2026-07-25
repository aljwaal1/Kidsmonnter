import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('BootReceiver remains private while retaining system restart actions', () {
    final manifest = File('native/AndroidManifest.xml').readAsStringSync();
    final receiverMatch = RegExp(
      r'<receiver\s+[^>]*android:name="\.BootReceiver"[\s\S]*?</receiver>',
    ).firstMatch(manifest);

    expect(receiverMatch, isNotNull);
    final receiver = receiverMatch!.group(0)!;

    expect(receiver, contains('android:exported="false"'));
    expect(
      receiver,
      contains('android.intent.action.BOOT_COMPLETED'),
    );
    expect(
      receiver,
      contains('android.intent.action.LOCKED_BOOT_COMPLETED'),
    );
    expect(
      receiver,
      contains('android.intent.action.MY_PACKAGE_REPLACED'),
    );
    expect(
      receiver,
      contains('com.explapp.kidstimeguard.RESTART_MONITOR'),
    );
  });
}
