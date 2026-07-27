from pathlib import Path

path = Path("tools/merge_extreme_lock_hardening.py")
source = path.read_text(encoding="utf-8")
marker = "EXTREME_LOCK_REAPPLY_PREPARATION_MARKER"
if marker in source:
    print("Extreme lock reapply preparation already installed")
    raise SystemExit(0)

old = '''native = NATIVE.read_text(encoding="utf-8")
if MARKER in native:
    print("Extreme lock hardening already merged")
    raise SystemExit(0)
'''
new = '''native = NATIVE.read_text(encoding="utf-8")
# EXTREME_LOCK_REAPPLY_PREPARATION_MARKER
_required_runtime_contracts = (
    "dispatchKeyEvent(event: KeyEvent)",
    "verifyEnteredPin(source: String)",
    "scheduleLockReassert()",
    "reassertStrictLock()",
    "LOCK_ACTIVITY_STARTED",
)
if MARKER in native and all(token in native for token in _required_runtime_contracts):
    print("Extreme lock hardening already merged and intact")
    raise SystemExit(0)
if MARKER in native:
    print("Extreme lock marker exists but runtime contract was overwritten; repairing")
'''
if old not in source:
    raise SystemExit("تعذر تجهيز إعادة تطبيق القفل الصارم: مقطع العلامة غير موجود")
path.write_text(source.replace(old, new, 1), encoding="utf-8")
print("Extreme lock reapply preparation installed")
