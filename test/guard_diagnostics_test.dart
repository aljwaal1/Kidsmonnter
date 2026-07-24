import 'package:flutter_test/flutter_test.dart';

import '../lib/guard_diagnostics.dart';

void main() {
  group('GuardDiagnostics', () {
    final now = DateTime.fromMillisecondsSinceEpoch(2_000_000);

    GuardDiagnostics diagnostics({
      required bool enabled,
      required bool overlayAllowed,
      required int heartbeatMs,
    }) {
      return GuardDiagnostics(
        protectionEnabled: enabled,
        overlayAllowed: overlayAllowed,
        serviceHeartbeatMs: heartbeatMs,
      );
    }

    test('reports disabled when protection is off', () {
      final value = diagnostics(
        enabled: false,
        overlayAllowed: true,
        heartbeatMs: now.millisecondsSinceEpoch,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.disabled);
      expect(value.readinessAt(now), GuardReadiness.disabled);
      expect(value.isReadyAt(now), isFalse);
    });

    test('reports starting when enabled without a heartbeat', () {
      final value = diagnostics(
        enabled: true,
        overlayAllowed: true,
        heartbeatMs: 0,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.starting);
      expect(value.readinessAt(now), GuardReadiness.starting);
      expect(value.heartbeatAgeAt(now), isNull);
    });

    test('reports ready for recent heartbeat and overlay permission', () {
      final value = diagnostics(
        enabled: true,
        overlayAllowed: true,
        heartbeatMs: now
            .subtract(const Duration(seconds: 10))
            .millisecondsSinceEpoch,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.healthy);
      expect(value.readinessAt(now), GuardReadiness.ready);
      expect(value.isReadyAt(now), isTrue);
      expect(value.heartbeatAgeAt(now), const Duration(seconds: 10));
    });

    test('reports missing overlay even when service is healthy', () {
      final value = diagnostics(
        enabled: true,
        overlayAllowed: false,
        heartbeatMs: now
            .subtract(const Duration(seconds: 5))
            .millisecondsSinceEpoch,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.healthy);
      expect(value.readinessAt(now), GuardReadiness.overlayMissing);
      expect(value.isReadyAt(now), isFalse);
    });

    test('reports stale service before evaluating overlay readiness', () {
      final value = diagnostics(
        enabled: true,
        overlayAllowed: false,
        heartbeatMs: now
            .subtract(const Duration(seconds: 20))
            .millisecondsSinceEpoch,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.stale);
      expect(value.readinessAt(now), GuardReadiness.serviceStale);
      expect(value.isReadyAt(now), isFalse);
    });

    test('treats a future heartbeat as healthy without negative age', () {
      final value = diagnostics(
        enabled: true,
        overlayAllowed: true,
        heartbeatMs: now.add(const Duration(seconds: 5)).millisecondsSinceEpoch,
      );

      expect(value.serviceHealthAt(now), GuardServiceHealth.healthy);
      expect(value.readinessAt(now), GuardReadiness.ready);
      expect(value.heartbeatAgeAt(now), Duration.zero);
    });

    test('marks heartbeat older than exactly 15 seconds as stale', () {
      final atBoundary = diagnostics(
        enabled: true,
        overlayAllowed: true,
        heartbeatMs: now
            .subtract(GuardDiagnostics.healthyHeartbeatWindow)
            .millisecondsSinceEpoch,
      );
      final afterBoundary = diagnostics(
        enabled: true,
        overlayAllowed: true,
        heartbeatMs: now
            .subtract(GuardDiagnostics.healthyHeartbeatWindow + const Duration(milliseconds: 1))
            .millisecondsSinceEpoch,
      );

      expect(atBoundary.serviceHealthAt(now), GuardServiceHealth.healthy);
      expect(afterBoundary.serviceHealthAt(now), GuardServiceHealth.stale);
    });
  });
}
