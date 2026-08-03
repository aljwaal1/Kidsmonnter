from pathlib import Path

path = Path("android/app/src/main/kotlin/com/explapp/kidstimeguard/MainActivity.kt")
text = path.read_text(encoding="utf-8")

replacements = {
    'return "$PIN_HASH_PREFIX$$PIN_HASH_ITERATIONS$$saltText$$hashText"':
        'return "${PIN_HASH_PREFIX}:${PIN_HASH_ITERATIONS}:$saltText:$hashText"',
    "val parts = encoded.split('$')": "val parts = encoded.split(':')",
    'storedHash.startsWith("$PIN_HASH_PREFIX$")':
        'storedHash.startsWith("$PIN_HASH_PREFIX:")',
    '''private fun isUnlockedForTrustedDay(prefs: SharedPreferences): Boolean =
    !prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false) &&
        isUnlockedForTrustedDay(prefs)''':
        '''private fun isUnlockedForTrustedDay(prefs: SharedPreferences): Boolean =
    !prefs.getBoolean(TIME_TAMPER_DETECTED_KEY, false) &&
        prefs.getString("unlocked_date", "") == today()''',
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Post-hardening fix expected one match, found {count}: {old[:80]}")
    text = text.replace(old, new, 1)

if 'PBKDF2WithHmacSHA256' not in text:
    raise SystemExit('PBKDF2 hardening marker missing')
if 'TIME_TAMPER_DETECTED' not in text:
    raise SystemExit('trusted-clock hardening marker missing')
if 'isUnlockedForTrustedDay(prefs)\n' in text.split('private fun isUnlockedForTrustedDay', 1)[1].split('\n\n', 1)[0]:
    raise SystemExit('trusted-day helper is recursive')

text += "\n// UNIFIED_SECURITY_HARDENING_V2_POSTFIX\n"
path.write_text(text, encoding="utf-8")
print('Post-hardening corrections applied successfully')
