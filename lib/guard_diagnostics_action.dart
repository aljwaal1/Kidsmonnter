import 'guard_diagnostics.dart';

enum GuardDiagnosticAction {
  none,
  refreshStatus,
  openOverlaySettings,
  restartProtectionService,
}

class GuardDiagnosticActionResolver {
  const GuardDiagnosticActionResolver._();

  static GuardDiagnosticAction forReadiness(GuardReadiness readiness) {
    switch (readiness) {
      case GuardReadiness.disabled:
      case GuardReadiness.ready:
        return GuardDiagnosticAction.none;
      case GuardReadiness.starting:
        return GuardDiagnosticAction.refreshStatus;
      case GuardReadiness.overlayMissing:
        return GuardDiagnosticAction.openOverlaySettings;
      case GuardReadiness.serviceStale:
        return GuardDiagnosticAction.restartProtectionService;
    }
  }

  static String labelFor(GuardDiagnosticAction action) {
    switch (action) {
      case GuardDiagnosticAction.none:
        return '';
      case GuardDiagnosticAction.refreshStatus:
        return 'إعادة الفحص';
      case GuardDiagnosticAction.openOverlaySettings:
        return 'تفعيل شاشة القفل';
      case GuardDiagnosticAction.restartProtectionService:
        return 'إعادة تشغيل الخدمة';
    }
  }
}
