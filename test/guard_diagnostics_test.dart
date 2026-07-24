import 'package:flutter_test/flutter_test.dart';

import '../lib/guard_diagnostics.dart';

void main() {
  group('GuardDiagnostics', () {
    final now = DateTime.fromMillisecondsSinceEpoch(2_000_000);

    test('reports disabled when protection is off', () {
      final diagnostics = GuardDiagnostics(
        protectionEnabled: false,
        serviceHeartbeatMs: now.millisecondsSinceEpoch,
      );

      expect(
        diagnostics.serviceHealthAt(now),
        GuardServiceHealth.disabled,
      );
    });

    test('reports starting when protection is enabled without heartbeat', () {
      const diagnostics = GuardDiagnostics(
        protectionEnabled: true,
        serviceHeartbeatMs: 0,
      );

      expect(
        diagnostics.serviceHealthAt(now),
        GuardServiceHealth.starting,
      );
      expect(diagnostics.heartbeatAgeAt(now), isNull);
    });

    test('reports healthy for a recent heartbeat', () {
      final diagnostics = GuardDiagnostics(
        protectionEnabled: true,
        serviceHeartbeatMs: now
            .subtract(const Duration(seconds: 10))
            .millisecondsSinceEpoch,
      );

      expect(
        diagnostics.serviceHealthAt(now),
        GuardServiceHealth.healthy,
      );
      expect(diagnostics.heartbeatAgeAt(now), const Duration(seconds: 10));
    });

    test('reports stale when heartbeat is older than the allowed window', () {
      final diagnostics = GuardDiagnostics(
        protectionEnabled: true,
        serviceHeartbeatMs: now
            .subtract(const Duration(seconds: 20))
            .millisecondsSinceEpoch,
      );

      expect(
        diagnostics.serviceHealthAt(now),
        GuardServiceHealth.stale,
      );
    });

    test('treats a future heartbeat as healthy without negative age', () {
      final diagnostics = GuardDiagnostics(
        protectionEnabled: true,
        serviceHeartbeatMs: now
            .add(const Duration(seconds: 5))
            .millisecondsSinceEpoch,
      );

      expect(
        diagnostics.serviceHealthAt(now),
        GuardServiceHealth.healthy,
      );
      expect(diagnostics.heartbeatAgeAt(now), Duration.zero);
    });
  });
}
