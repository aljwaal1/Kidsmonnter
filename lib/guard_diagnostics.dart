enum GuardServiceHealth {
  disabled,
  starting,
  healthy,
  stale,
}

class GuardDiagnostics {
  const GuardDiagnostics({
    required this.protectionEnabled,
    required this.serviceHeartbeatMs,
  });

  static const Duration healthyHeartbeatWindow = Duration(seconds: 15);
  static const Duration startingHeartbeatWindow = Duration(seconds: 30);

  final bool protectionEnabled;
  final int serviceHeartbeatMs;

  GuardServiceHealth serviceHealthAt(DateTime now) {
    if (!protectionEnabled) return GuardServiceHealth.disabled;
    if (serviceHeartbeatMs <= 0) return GuardServiceHealth.starting;

    final heartbeat = DateTime.fromMillisecondsSinceEpoch(serviceHeartbeatMs);
    final age = now.difference(heartbeat);

    if (age.isNegative || age <= healthyHeartbeatWindow) {
      return GuardServiceHealth.healthy;
    }
    return GuardServiceHealth.stale;
  }

  Duration? heartbeatAgeAt(DateTime now) {
    if (serviceHeartbeatMs <= 0) return null;
    final heartbeat = DateTime.fromMillisecondsSinceEpoch(serviceHeartbeatMs);
    final age = now.difference(heartbeat);
    return age.isNegative ? Duration.zero : age;
  }
}
