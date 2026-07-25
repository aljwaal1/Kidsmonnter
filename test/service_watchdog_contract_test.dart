import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MonitorService watchdog contract', () {
    late String nativeSource;

    setUpAll(() {
      nativeSource = File('native/MainActivityV2.kt').readAsStringSync();
    });

    test('uses a broadcast watchdog instead of directly restarting a service alarm', () {
      expect(nativeSource, contains('PendingIntent.getBroadcast'));
      expect(nativeSource, isNot(contains('PendingIntent.getService')));
      expect(nativeSource, contains('MONITOR_WATCHDOG_ACTION'));
    });

    test('checks heartbeat freshness before restarting the service', () {
      expect(nativeSource, contains('STALE_HEARTBEAT_MS'));
      expect(nativeSource, contains('heartbeatAge > STALE_HEARTBEAT_MS'));
      expect(
        nativeSource,
        contains(
          'context.requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)',
        ),
      );
      expect(
        nativeSource,
        isNot(contains('if (serviceNeedsRestart) context.startMonitorServiceSafely()')),
      );
    });

    test('reschedules the watchdog after every receiver execution', () {
      expect(nativeSource, contains('context.scheduleMonitorWatchdog()'));
      expect(nativeSource, contains('scheduleMonitorWatchdog(2_000L)'));
    });
  });
}
