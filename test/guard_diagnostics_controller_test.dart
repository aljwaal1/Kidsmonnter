import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kidsmonnter/guard_diagnostics_action.dart';
import 'package:kidsmonnter/guard_diagnostics_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('kidsmonnter/test-control');
  final calls = <MethodCall>[];
  var refreshCount = 0;

  setUp(() {
    calls.clear();
    refreshCount = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      return null;
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  GuardDiagnosticsController createController() {
    return GuardDiagnosticsController(
      channel: channel,
      refreshStatus: () async {
        refreshCount += 1;
      },
    );
  }

  test('none does not call native code or refresh status', () async {
    await createController().resolve(
      GuardDiagnosticAction.none,
      dailyMinutes: 60,
    );

    expect(calls, isEmpty);
    expect(refreshCount, 0);
  });

  test('refreshStatus refreshes without invoking native code', () async {
    await createController().resolve(
      GuardDiagnosticAction.refreshStatus,
      dailyMinutes: 60,
    );

    expect(calls, isEmpty);
    expect(refreshCount, 1);
  });

  test('openOverlaySettings invokes the matching native method', () async {
    await createController().resolve(
      GuardDiagnosticAction.openOverlaySettings,
      dailyMinutes: 60,
    );

    expect(calls, hasLength(1));
    expect(calls.single.method, 'openOverlaySettings');
    expect(refreshCount, 0);
  });

  test('restartProtectionService invokes only the dedicated native method',
      () async {
    await createController().resolve(
      GuardDiagnosticAction.restartProtectionService,
      dailyMinutes: 90,
    );

    expect(calls, hasLength(1));
    expect(calls.single.method, 'restartProtectionService');
    expect(calls.single.arguments, isNull);
    expect(refreshCount, 1);
  });

  test('restartProtectionService does not reuse startProtection', () async {
    await createController().resolve(
      GuardDiagnosticAction.restartProtectionService,
      dailyMinutes: 0,
    );

    expect(calls.map((call) => call.method), isNot(contains('startProtection')));
    expect(refreshCount, 1);
  });
}
