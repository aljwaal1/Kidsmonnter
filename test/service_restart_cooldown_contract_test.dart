import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('service recovery requests are throttled until a heartbeat succeeds', () {
    final source = File('native/MainActivityV2.kt').readAsStringSync();

    expect(source, contains('SERVICE_START_REQUEST_COOLDOWN_MS = 15_000L'));
    expect(source, contains('requestMonitorServiceStartIfAllowed'));
    expect(
      source,
      contains('requestMonitorServiceStartIfAllowed(prefs)'),
    );
    expect(
      source,
      contains(
        'requestMonitorServiceStartIfAllowed(prefs, force = !isWatchdog)',
      ),
    );
    expect(
      source,
      contains('remove(LAST_SERVICE_START_REQUEST_ELAPSED_KEY)'),
    );
    expect(
      source,
      contains('now - lastRequest < SERVICE_START_REQUEST_COOLDOWN_MS'),
    );
  });
}
