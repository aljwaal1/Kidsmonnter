enum GuardServiceHealth {
  disabled,
  starting,
  healthy,
  stale,
}

enum GuardReadiness {
  disabled,
  starting,
  ready,
  overlayMissing,
  serviceStale,
}

class GuardDiagnostics {
  const GuardDiagnostics({
    required this.protectionEnabled,
    required this.overlayAllowed,
    required this.serviceHeartbeatMs,
  });

  static const Duration healthyHeartbeatWindow = Duration(seconds: 15);
  static const Duration allowedFutureClockSkew = Duration(seconds: 5);

  final bool protectionEnabled;
  final bool overlayAllowed;
  final int serviceHeartbeatMs;

  GuardServiceHealth serviceHealthAt(DateTime now) {
    if (!protectionEnabled) return GuardServiceHealth.disabled;
    if (serviceHeartbeatMs <= 0) return GuardServiceHealth.starting;

    final heartbeat = DateTime.fromMillisecondsSinceEpoch(serviceHeartbeatMs);
    final age = now.difference(heartbeat);

    if (age < -allowedFutureClockSkew) {
      return GuardServiceHealth.stale;
    }
    if (age.isNegative || age <= healthyHeartbeatWindow) {
      return GuardServiceHealth.healthy;
    }
    return GuardServiceHealth.stale;
  }

  GuardReadiness readinessAt(DateTime now) {
    final health = serviceHealthAt(now);
    switch (health) {
      case GuardServiceHealth.disabled:
        return GuardReadiness.disabled;
      case GuardServiceHealth.starting:
        return GuardReadiness.starting;
      case GuardServiceHealth.stale:
        return GuardReadiness.serviceStale;
      case GuardServiceHealth.healthy:
        return overlayAllowed ? GuardReadiness.ready : GuardReadiness.overlayMissing;
    }
  }

  Duration? heartbeatAgeAt(DateTime now) {
    if (serviceHeartbeatMs <= 0) return null;
    final heartbeat = DateTime.fromMillisecondsSinceEpoch(serviceHeartbeatMs);
    final age = now.difference(heartbeat);
    return age.isNegative ? Duration.zero : age;
  }

  bool isReadyAt(DateTime now) => readinessAt(now) == GuardReadiness.ready;
}
