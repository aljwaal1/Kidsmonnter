import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يسجل دورة خدمة الخلفية ويحمي العداد من التوقف', () {
    final native = File('native/MainActivityV2.kt').readAsStringSync();
    final dart = File('lib/main.dart').readAsStringSync();

    expect(native, contains('RUNTIME_DIAGNOSTICS_MARKER'));
    expect(native, contains('kidsmonnter-diagnostic.log'));
    expect(native, contains('SERVICE_CREATED'));
    expect(native, contains('SERVICE_FOREGROUND_READY'));
    expect(native, contains('SERVICE_START_COMMAND'));
    expect(native, contains('SERVICE_HEARTBEAT'));
    expect(native, contains('USAGE_ACCOUNTED'));
    expect(native, contains('SERVICE_TASK_REMOVED'));
    expect(native, contains('SERVICE_DESTROYED'));
    expect(native, contains('BOOT_RECEIVER'));
    expect(native, contains('WATCHDOG_DECISION'));
    expect(native, contains('LOCK_CREATE_ATTEMPT'));
    expect(native, contains('LOCK_CREATED'));
    expect(native, contains('LOCK_CREATE_FAILED'));
    expect(native, contains('TICK_ERROR'));
    expect(native, contains('finally {\n                handler.postDelayed(this, 1000L)'));
    expect(native, contains('"getDiagnosticLog"'));
    expect(native, contains('"clearDiagnosticLog"'));

    expect(dart, contains('RUNTIME_DIAGNOSTICS_UI_MARKER'));
    expect(dart, contains("invokeMethod<String>('getDiagnosticLog')"));
    expect(dart, contains("invokeMethod<void>('clearDiagnosticLog')"));
    expect(dart, contains('Clipboard.setData'));
    expect(dart, contains('سجل تشخيص التطبيق'));
  });
}
