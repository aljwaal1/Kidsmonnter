import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kidsmonnter/guard_diagnostics.dart';
import 'package:kidsmonnter/guard_diagnostics_action.dart';
import 'package:kidsmonnter/guard_diagnostics_card.dart';

void main() {
  final now = DateTime.fromMillisecondsSinceEpoch(2000000);

  Widget buildCard(
    GuardDiagnostics diagnostics, {
    ValueChanged<GuardDiagnosticAction>? onResolveIssue,
  }) {
    return MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: Scaffold(
          body: GuardDiagnosticsCard(
            diagnostics: diagnostics,
            now: now,
            onResolveIssue: onResolveIssue,
          ),
        ),
      ),
    );
  }

  testWidgets('تعرض أن الحماية جاهزة عند حداثة النبضة ووجود Overlay', (tester) async {
    await tester.pumpWidget(
      buildCard(
        GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: true,
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 5000,
        ),
      ),
    );

    expect(find.text('الحماية جاهزة'), findsOneWidget);
    expect(find.textContaining('آخر إشارة منذ 5 ثانية'), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
  });

  testWidgets('توجه إلى إعدادات Overlay عند نقص صلاحية شاشة القفل', (tester) async {
    GuardDiagnosticAction? receivedAction;
    await tester.pumpWidget(
      buildCard(
        GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: false,
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 2000,
        ),
        onResolveIssue: (action) => receivedAction = action,
      ),
    );

    expect(find.text('شاشة القفل غير جاهزة'), findsOneWidget);
    expect(find.text('تفعيل شاشة القفل'), findsOneWidget);

    await tester.tap(find.text('تفعيل شاشة القفل'));
    await tester.pump();
    expect(receivedAction, GuardDiagnosticAction.openOverlaySettings);
  });

  testWidgets('توجه إلى إعادة تشغيل الخدمة عند قدم النبضة', (tester) async {
    GuardDiagnosticAction? receivedAction;
    await tester.pumpWidget(
      buildCard(
        GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: true,
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 20000,
        ),
        onResolveIssue: (action) => receivedAction = action,
      ),
    );

    expect(find.text('خدمة الخلفية لا تستجيب'), findsOneWidget);
    expect(find.textContaining('20 ثانية'), findsOneWidget);
    expect(find.text('إعادة تشغيل الخدمة'), findsOneWidget);

    await tester.tap(find.text('إعادة تشغيل الخدمة'));
    await tester.pump();
    expect(receivedAction, GuardDiagnosticAction.restartProtectionService);
  });

  testWidgets('توجه إلى إعادة الفحص أثناء انتظار أول نبضة', (tester) async {
    GuardDiagnosticAction? receivedAction;
    await tester.pumpWidget(
      buildCard(
        const GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: true,
          serviceHeartbeatMs: 0,
        ),
        onResolveIssue: (action) => receivedAction = action,
      ),
    );

    expect(find.text('إعادة الفحص'), findsOneWidget);
    await tester.tap(find.text('إعادة الفحص'));
    await tester.pump();
    expect(receivedAction, GuardDiagnosticAction.refreshStatus);
  });
}
