import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Native protection contract', () {
    late String manifest;
    late String nativeEngine;

    setUpAll(() {
      manifest = File('native/AndroidManifest.xml').readAsStringSync();
      nativeEngine = File('native/MainActivityV2.kt').readAsStringSync();
    });

    test('keeps private protection data out of Android backups', () {
      expect(manifest, contains('android:allowBackup="false"'));
      expect(manifest, contains('android:usesCleartextTraffic="false"'));
    });

    test('declares the persistent foreground monitoring service', () {
      expect(
        manifest,
        contains('android:name=".MonitorService"'),
      );
      expect(manifest, contains('android:stopWithTask="false"'));
      expect(
        manifest,
        contains('android:foregroundServiceType="specialUse"'),
      );
      expect(
        manifest,
        contains('parental_control_screen_time_monitoring'),
      );
    });

    test('restores protection after boot, update, or task removal', () {
      expect(manifest, contains('android.intent.action.BOOT_COMPLETED'));
      expect(manifest, contains('android.intent.action.MY_PACKAGE_REPLACED'));
      expect(nativeEngine, contains('return START_STICKY'));
      expect(nativeEngine, contains('override fun onTaskRemoved'));
      expect(nativeEngine, contains('scheduleRestart()'));
    });

    test('accounts elapsed screen-on time outside the Flutter UI', () {
      expect(nativeEngine, contains('SystemClock.elapsedRealtime()'));
      expect(nativeEngine, contains('private fun accountElapsedUsage()'));
      expect(nativeEngine, contains('if (!screenOn || !prefs.getBoolean("enabled", false)) return'));
      expect(nativeEngine, contains('.putInt("used_seconds", after)'));
    });

    test('keeps uninstall protection limited to device-owner mode', () {
      expect(nativeEngine, contains('isDeviceOwnerApp(packageName)'));
      expect(nativeEngine, contains('setUninstallBlocked(admin, packageName, true)'));
      expect(manifest, contains('android.permission.BIND_DEVICE_ADMIN'));
    });
  });
}
