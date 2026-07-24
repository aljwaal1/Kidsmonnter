import 'guard_diagnostics.dart';

/// لقطة واحدة لحالة الحماية كما ترسلها طبقة Android Native.
///
/// أبقي هذا النموذج مستقلًا عن الواجهة حتى يمكن اختباره واستخدامه في
/// التشخيص دون الاعتماد على Widgets أو MethodChannel.
class GuardStatus {
  const GuardStatus({
    required this.enabled,
    required this.overlayAllowed,
    required this.hasPin,
    required this.usedSeconds,
    required this.dailyMinutes,
    required this.failedAttempts,
    required this.parentEmail,
    required this.serviceHeartbeatMs,
  });

  final bool enabled;
  final bool overlayAllowed;
  final bool hasPin;
  final int usedSeconds;
  final int dailyMinutes;
  final int failedAttempts;
  final String parentEmail;
  final int serviceHeartbeatMs;

  factory GuardStatus.fromMap(
    Map<String, dynamic> map,
    bool overlayAllowed,
  ) {
    return GuardStatus(
      enabled: map['enabled'] == true,
      overlayAllowed: overlayAllowed,
      hasPin: map['hasPin'] == true,
      usedSeconds: _nonNegativeInt(map['usedSeconds']),
      dailyMinutes: _boundedDailyMinutes(map['dailyMinutes']),
      failedAttempts: _nonNegativeInt(map['failedAttempts']),
      parentEmail: map['parentEmail']?.toString().trim() ?? '',
      serviceHeartbeatMs: _nonNegativeInt(map['serviceHeartbeatMs']),
    );
  }

  GuardDiagnostics get diagnostics => GuardDiagnostics(
        protectionEnabled: enabled,
        overlayAllowed: overlayAllowed,
        serviceHeartbeatMs: serviceHeartbeatMs,
      );

  static int _nonNegativeInt(Object? value) {
    final parsed = value is num ? value.toInt() : int.tryParse('$value');
    return (parsed ?? 0).clamp(0, 1 << 62);
  }

  static int _boundedDailyMinutes(Object? value) {
    final parsed = value is num ? value.toInt() : int.tryParse('$value');
    return (parsed ?? 60).clamp(1, 1440);
  }
}
