import 'package:flutter_test/flutter_test.dart';

import '../lib/main.dart';

void main() {
  group('GuardStatus', () {
    test('parses complete native status payload', () {
      final status = GuardStatus.fromMap(
        <String, dynamic>{
          'enabled': true,
          'usedSeconds': 125,
          'dailyMinutes': 90,
          'hasPin': true,
          'failedAttempts': 3,
          'parentEmail': 'parent@example.com',
        },
        true,
      );

      expect(status.enabled, isTrue);
      expect(status.overlayAllowed, isTrue);
      expect(status.hasPin, isTrue);
      expect(status.usedSeconds, 125);
      expect(status.dailyMinutes, 90);
      expect(status.failedAttempts, 3);
      expect(status.parentEmail, 'parent@example.com');
    });

    test('uses safe defaults for missing native values', () {
      final status = GuardStatus.fromMap(<String, dynamic>{}, false);

      expect(status.enabled, isFalse);
      expect(status.overlayAllowed, isFalse);
      expect(status.hasPin, isFalse);
      expect(status.usedSeconds, 0);
      expect(status.dailyMinutes, 60);
      expect(status.failedAttempts, 0);
      expect(status.parentEmail, isEmpty);
    });

    test('accepts numeric values returned as non-int numbers', () {
      final status = GuardStatus.fromMap(
        <String, dynamic>{
          'usedSeconds': 61.0,
          'dailyMinutes': 30.0,
          'failedAttempts': 2.0,
        },
        false,
      );

      expect(status.usedSeconds, 61);
      expect(status.dailyMinutes, 30);
      expect(status.failedAttempts, 2);
    });
  });
}
