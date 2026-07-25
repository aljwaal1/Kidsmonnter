from pathlib import Path

native_path = Path("native/MainActivityV2.kt")
source = native_path.read_text(encoding="utf-8")

helper = '''private fun Context.guardNotificationContentIntent(): PendingIntent =
    PendingIntent.getActivity(
        this,
        1003,
        Intent(this, MainActivity::class.java).addFlags(
            Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        ),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
    )

'''

if "guardNotificationContentIntent" not in source:
    marker = "private fun shouldRecoverProtectionService"
    if marker not in source:
        raise SystemExit("Could not find notification helper insertion point")
    source = source.replace(marker, helper + marker, 1)

content_intent = ".setContentIntent(guardNotificationContentIntent())"
if content_intent not in source:
    marker = '.setContentTitle("حارس وقت الأطفال")'
    if marker not in source:
        raise SystemExit("Could not find guard notification builder")
    source = source.replace(marker, content_intent + "\n            " + marker, 1)

native_path.write_text(source, encoding="utf-8")
