import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('تفصل نبضة العرض عن نبضة الاستعادة الرتيبة', () {
    final patch = File('tools/post_harden_fix.py').readAsStringSync();
    final diagnostics = File('lib/guard_diagnostics.dart').readAsStringSync();

    expect(patch, contains('HEARTBEAT_ELAPSED_KEY'));
    expect(patch, contains('System.currentTimeMillis()'));
    expect(patch, contains('SystemClock.elapsedRealtime()'));
    expect(patch, contains('DUAL_HEARTBEAT_CLOCK_FIX'));

    // Flutter يتوقع طابعًا زمنيًا ميلاديًا لعرض عمر النبضة.
    expect(
      diagnostics,
      contains('DateTime.fromMillisecondsSinceEpoch(serviceHeartbeatMs)'),
    );
  });
}

// BUILD_TRIGGER_HEARTBEAT_FIX_2026_08_04
