import 'package:flutter/services.dart';

import 'guard_diagnostics_action.dart';

/// ينفذ إجراءات بطاقة التشخيص عبر واجهة صغيرة قابلة للاختبار.
///
/// لا يحتوي على منطق عرض، ولا يغيّر حالة الحماية مباشرة إلا عند طلب
/// إعادة تشغيل الخدمة؛ عندها يعيد استدعاء startProtection بالمدة الحالية.
class GuardDiagnosticsController {
  GuardDiagnosticsController({
    required MethodChannel channel,
    required Future<void> Function() refreshStatus,
  })  : _channel = channel,
        _refreshStatus = refreshStatus;

  final MethodChannel _channel;
  final Future<void> Function() _refreshStatus;

  Future<void> resolve(
    GuardDiagnosticAction action, {
    required int dailyMinutes,
  }) async {
    switch (action) {
      case GuardDiagnosticAction.none:
        return;
      case GuardDiagnosticAction.refreshStatus:
        await _refreshStatus();
        return;
      case GuardDiagnosticAction.openOverlaySettings:
        await _channel.invokeMethod<void>('openOverlaySettings');
        return;
      case GuardDiagnosticAction.restartProtectionService:
        await _channel.invokeMethod<void>(
          'startProtection',
          <String, Object>{'minutes': dailyMinutes.clamp(1, 1440)},
        );
        await _refreshStatus();
        return;
    }
  }
}
