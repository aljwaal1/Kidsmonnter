import 'package:flutter_test/flutter_test.dart';
import 'package:kidsmonnter/guard_diagnostics.dart';
import 'package:kidsmonnter/guard_diagnostics_presentation.dart';

void main() {
  group('GuardDiagnosticPresentation', () {
    test('disabled state is neutral and does not demand action', () {
      final presentation = GuardDiagnosticPresentation.fromReadiness(
        GuardReadiness.disabled,
      );

      expect(presentation.title, 'الحماية متوقفة');
      expect(presentation.tone, GuardDiagnosticTone.neutral);
      expect(presentation.actionRequired, isFalse);
    });

    test('ready state includes recent heartbeat age', () {
      final presentation = GuardDiagnosticPresentation.fromReadiness(
        GuardReadiness.ready,
        heartbeatAge: const Duration(seconds: 7),
      );

      expect(presentation.title, 'الحماية جاهزة');
      expect(presentation.message, contains('7 ثانية'));
      expect(presentation.tone, GuardDiagnosticTone.success);
      expect(presentation.actionRequired, isFalse);
    });

    test('missing overlay clearly requires user action', () {
      final presentation = GuardDiagnosticPresentation.fromReadiness(
        GuardReadiness.overlayMissing,
      );

      expect(presentation.title, 'شاشة القفل غير جاهزة');
      expect(presentation.message, contains('الظهور فوق التطبيقات'));
      expect(presentation.tone, GuardDiagnosticTone.warning);
      expect(presentation.actionRequired, isTrue);
    });

    test('stale service reports minutes without rounding up', () {
      final presentation = GuardDiagnosticPresentation.fromReadiness(
        GuardReadiness.serviceStale,
        heartbeatAge: const Duration(minutes: 3, seconds: 59),
      );

      expect(presentation.title, 'خدمة الخلفية لا تستجيب');
      expect(presentation.message, contains('3 دقيقة'));
      expect(presentation.tone, GuardDiagnosticTone.danger);
      expect(presentation.actionRequired, isTrue);
    });

    test('starting state remains informational', () {
      final presentation = GuardDiagnosticPresentation.fromReadiness(
        GuardReadiness.starting,
      );

      expect(presentation.title, 'جاري تشغيل خدمة الحماية');
      expect(presentation.tone, GuardDiagnosticTone.warning);
      expect(presentation.actionRequired, isFalse);
    });
  });
}
