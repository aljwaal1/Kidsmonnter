from pathlib import Path

path = Path('tools/strict_parental_mode.py')
text = path.read_text(encoding='utf-8')
old = '''old_enable = \'\'\'                        .putBoolean("enabled", true)\n                        .putString("date", today())\'\'\'\nnew_enable = \'\'\'                        .putBoolean("enabled", true)\n                        .putBoolean("strict_mode", true)\n                        .putString("date", today())\'\'\'\nif old_enable not in kotlin:\n    raise SystemExit(\'Protection enable preferences block was not found\')\nkotlin = kotlin.replace(old_enable, new_enable, 1)\n'''
new = '''enable_pattern = re.compile(\n    r'(\\.putBoolean\\("enabled", true\\)\\n)(?!\\s*\\.putBoolean\\("strict_mode", true\\))'\n)\nkotlin, enable_count = enable_pattern.subn(\n    r'\\1                        .putBoolean("strict_mode", true)\\n',\n    kotlin,\n    count=1,\n)\nif enable_count != 1:\n    raise SystemExit(f'Protection enable preference insertion count={enable_count}')\n'''
if old not in text:
    raise SystemExit('Expected strict-mode compatibility block was not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Strict parental script compatibility patch applied')
