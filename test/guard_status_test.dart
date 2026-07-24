import 'package:flutter_test/flutter_test.dart';

import '../lib/guard_diagnostics.dart';
import '../lib/guard_status.dart';

void main() {
  group('GuardStatus', () {
    test('parses complete native status payload including heartbeat', () {
      final status = GuardStatus.fromMap(
        <String, dynamic>{
          'enabled': true,
          'usedSeconds': 125,
          'dailyMinutes': 90,
          'hasPin': true,
          'failedAttempts': 3,
          'parentEmail': ' parent@example.com ',
          'serviceHeartbeatMs': 1710000000000,
        },
        true,
      );

      expect(status.enabled, isTrue);
      expect(status.overlayAllowed, isTrue);
      expect(status.hasPin, isTrue);
      expect(status.usedSeconds, 125);
      expect(status.dailyMinutes, 90);
      expect(status.failedAttempts, 3);
      expect(status.parentEmail, 'parent@example.com');
      expect(status.serviceHeartbeatMs, 1710000000000);
    });

    test('uses safe defaults for missing native values', () {
      final status = GuardStatus.fromMap(<String, dynamic>{}, false);

      expect(status.enabled, isFalse);
      expect(status.overlayAllowed, isFalse);
      expect(status.hasPin, isFalse);
      expect(status.usedSeconds, 0);
      expect(status.dailyMinutes, 60);
      expect(status.failedAttempts, 0);
      expect(status.parentEmail, isEmpty);
      expect(status.serviceHeartbeatMs, 0);
    });

    test('accepts numeric and numeric-string values safely', () {
      final status = GuardStatus.fromMap(
        <String, dynamic>{
          'usedSeconds': 61.0,
          'dailyMinutes': '30',
          'failedAttempts': 2.0,
          'serviceHeartbeatMs': '1710000000000',
        },
        false,
      );

      expect(status.usedSeconds, 61);
      expect(status.dailyMinutes, 30);
      expect(status.failedAttempts, 2);
      expect(status.serviceHeartbeatMs, 1710000000000);
    });

    test('clamps invalid counters and daily duration', () {
      final tooSmall = GuardStatus.fromMap(
        <String, dynamic>{
          'usedSeconds': -20,
          'dailyMinutes': 0,
          'failedAttempts': -3,
          'serviceHeartbeatMs': -1,
        },
        false,
      );
      final tooLarge = GuardStatus.fromMap(
        <String, dynamic>{'dailyMinutes': 2000},
        false,
      );

      expect(tooSmall.usedSeconds, 0);
      expect(tooSmall.failedAttempts, 0);
      expect(tooSmall.serviceHeartbeatMs, 0);
      expect(tooSmall.dailyMinutes, 1);
      expect(tooLarge.dailyMinutes, 1440);
    });

    test('builds diagnostics from the same immutable status snapshot', () {
      final now = DateTime.fromMillisecondsSinceEpoch(1710000005000);
      final status = GuardStatus.fromMap(
        <String, dynamic>{
          'enabled': true,
          'serviceHeartbeatMs': 1710000000000,
        },
        true,
      );

      expect(status.diagnostics.readinessAt(now), GuardReadiness.ready);
    });
  });
}
