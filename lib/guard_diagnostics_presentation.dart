import 'guard_diagnostics.dart';

enum GuardDiagnosticTone {
  neutral,
  success,
  warning,
  danger,
}

class GuardDiagnosticPresentation {
  const GuardDiagnosticPresentation({
    required this.title,
    required this.message,
    required this.tone,
    required this.actionRequired,
  });

  final String title;
  final String message;
  final GuardDiagnosticTone tone;
  final bool actionRequired;

  factory GuardDiagnosticPresentation.fromReadiness(
    GuardReadiness readiness, {
    Duration? heartbeatAge,
  }) {
    switch (readiness) {
      case GuardReadiness.disabled:
        return const GuardDiagnosticPresentation(
          title: 'الحماية متوقفة',
          message: 'فعّل الحماية لبدء عداد الاستخدام وخدمة الخلفية.',
          tone: GuardDiagnosticTone.neutral,
          actionRequired: false,
        );
      case GuardReadiness.starting:
        return const GuardDiagnosticPresentation(
          title: 'جاري تشغيل خدمة الحماية',
          message: 'انتظر بضع ثوانٍ حتى تصل أول إشارة من خدمة الخلفية.',
          tone: GuardDiagnosticTone.warning,
          actionRequired: false,
        );
      case GuardReadiness.ready:
        return GuardDiagnosticPresentation(
          title: 'الحماية جاهزة',
          message: heartbeatAge == null
              ? 'خدمة الخلفية وشاشة القفل تعملان بصورة طبيعية.'
              : 'خدمة الخلفية سليمة. آخر إشارة منذ ${_ageLabel(heartbeatAge)}.',
          tone: GuardDiagnosticTone.success,
          actionRequired: false,
        );
      case GuardReadiness.overlayMissing:
        return const GuardDiagnosticPresentation(
          title: 'شاشة القفل غير جاهزة',
          message: 'العداد يعمل، لكن يجب منح صلاحية الظهور فوق التطبيقات حتى يظهر القفل.',
          tone: GuardDiagnosticTone.warning,
          actionRequired: true,
        );
      case GuardReadiness.serviceStale:
        return GuardDiagnosticPresentation(
          title: 'خدمة الخلفية لا تستجيب',
          message: heartbeatAge == null
              ? 'لم تصل إشارة حديثة من خدمة الحماية.'
              : 'آخر إشارة من خدمة الحماية كانت منذ ${_ageLabel(heartbeatAge)}.',
          tone: GuardDiagnosticTone.danger,
          actionRequired: true,
        );
    }
  }

  static String _ageLabel(Duration age) {
    if (age.inSeconds < 60) return '${age.inSeconds} ثانية';
    if (age.inMinutes < 60) return '${age.inMinutes} دقيقة';
    return '${age.inHours} ساعة';
  }
}
