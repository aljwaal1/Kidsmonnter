import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kidsmonnter/guard_diagnostics.dart';
import 'package:kidsmonnter/guard_diagnostics_card.dart';

void main() {
  final now = DateTime.fromMillisecondsSinceEpoch(2_000_000);

  Widget buildCard(
    GuardDiagnostics diagnostics, {
    VoidCallback? onResolveIssue,
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
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 5_000,
        ),
      ),
    );

    expect(find.text('الحماية جاهزة'), findsOneWidget);
    expect(find.textContaining('آخر إشارة منذ 5 ثانية'), findsOneWidget);
    expect(find.text('معالجة المشكلة'), findsNothing);
  });

  testWidgets('تعرض إجراءً عند نقص صلاحية شاشة القفل', (tester) async {
    var pressed = false;
    await tester.pumpWidget(
      buildCard(
        GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: false,
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 2_000,
        ),
        onResolveIssue: () => pressed = true,
      ),
    );

    expect(find.text('شاشة القفل غير جاهزة'), findsOneWidget);
    expect(find.text('معالجة المشكلة'), findsOneWidget);

    await tester.tap(find.text('معالجة المشكلة'));
    await tester.pump();
    expect(pressed, isTrue);
  });

  testWidgets('تعرض تعطل الخدمة عند قدم النبضة', (tester) async {
    await tester.pumpWidget(
      buildCard(
        GuardDiagnostics(
          protectionEnabled: true,
          overlayAllowed: true,
          serviceHeartbeatMs: now.millisecondsSinceEpoch - 20_000,
        ),
      ),
    );

    expect(find.text('خدمة الخلفية لا تستجيب'), findsOneWidget);
    expect(find.textContaining('20 ثانية'), findsOneWidget);
  });
}
