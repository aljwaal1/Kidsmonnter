from pathlib import Path

path = Path('lib/main.dart')
text = path.read_text(encoding='utf-8')
old = """  Future<void> _setProtection(bool value) async {
    if (value) {
      if (!await _ensurePin()) return;
      if (!_overlayAllowed) {
        await _channel.invokeMethod('openOverlaySettings');
        _message('فعّل الظهور فوق التطبيقات، ثم ارجع واضغط تفعيل.');
        return;
      }
      await _channel.invokeMethod('startProtection', {'minutes': _dailyMinutes});
    } else {
      final pin = await _askPin(title: 'إيقاف الحماية');
      if (pin == null) return;
      try {
        await _channel.invokeMethod('stopProtection', {'pin': pin});
      } on PlatformException {
        _message('رمز ولي الأمر غير صحيح، وتم تسجيل المحاولة.');
      }
    }
    await _loadStatus();
  }
"""
new = """  Future<void> _setProtection(bool value) async {
    try {
      if (value) {
        if (!await _ensurePin()) return;

        // فعّل الخدمة أولًا حتى لا يبدو المفتاح معطلًا بسبب صلاحية Overlay.
        await _channel.invokeMethod('startProtection', {'minutes': _dailyMinutes});
        await _loadStatus();
        _message('تم تفعيل الحماية والعداد يعمل الآن.');

        if (!_overlayAllowed) {
          await _channel.invokeMethod('openOverlaySettings');
          _message('الحماية مفعّلة. اسمح بالظهور فوق التطبيقات حتى تعمل شاشة القفل.');
        }
      } else {
        final pin = await _askPin(title: 'إيقاف الحماية');
        if (pin == null) return;
        await _channel.invokeMethod('stopProtection', {'pin': pin});
        await _loadStatus();
        _message('تم إيقاف الحماية.');
      }
    } on PlatformException catch (error) {
      await _loadStatus();
      _message(error.message ?? 'تعذر تغيير حالة الحماية.');
    }
  }
"""
if old not in text:
    raise SystemExit('Activation block not found; refusing unsafe patch')
path.write_text(text.replace(old, new), encoding='utf-8')
