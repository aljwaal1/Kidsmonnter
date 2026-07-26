import ast
from pathlib import Path

NATIVE_PATH = Path("native/MainActivityV2.kt")
TEMPLATE_PATH = Path("tools/merge_background_lock_overlay.py")
MARKER = "BACKGROUND_LOCK_OVERLAY_MARKER"


def load_overlay_block() -> str:
    tree = ast.parse(TEMPLATE_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "new_lock":
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, str) or MARKER not in value:
                        break
                    return value
    raise SystemExit("تعذر قراءة قالب نافذة القفل التلقائي")


source = NATIVE_PATH.read_text(encoding="utf-8")
if MARKER in source:
    print("قفل الخلفية التلقائي مدمج مسبقاً")
    raise SystemExit(0)

if "import android.graphics.PixelFormat\n" not in source:
    anchor = "import android.graphics.Color\n"
    if anchor not in source:
        raise SystemExit("تعذر دمج PixelFormat: لم يوجد استيراد Color")
    source = source.replace(anchor, anchor + "import android.graphics.PixelFormat\n", 1)

field_anchor = "    private var lastLockLaunchElapsedMs = 0L\n"
field_block = (
    field_anchor
    + "    private var lockOverlayView: View? = null\n"
    + "    private var lockWindowManager: WindowManager? = null\n"
    + "    private val lockOverlayPin = StringBuilder(6)\n"
    + "    private var lockOverlayPinDisplay: TextView? = null\n"
    + "    private var lockOverlayStatus: TextView? = null\n"
    + "    private var lockOverlayActionButtons: List<Button> = emptyList()\n"
)
if "private var lockOverlayView: View?" not in source:
    if field_anchor not in source:
        raise SystemExit("تعذر دمج حالة نافذة القفل: لم يوجد مرساة المهلة")
    source = source.replace(field_anchor, field_block, 1)

cleanup_anchor = "        accountElapsedUsage()\n        handler.removeCallbacks(ticker)\n"
cleanup_block = "        accountElapsedUsage()\n        dismissLockOverlay()\n        handler.removeCallbacks(ticker)\n"
if cleanup_block not in source:
    if cleanup_anchor not in source:
        raise SystemExit("تعذر دمج تنظيف نافذة القفل عند إيقاف الخدمة")
    source = source.replace(cleanup_anchor, cleanup_block, 1)

start_anchor = "    private fun enforceLockIfNeeded() {"
end_anchor = "    private fun monitorOverlayPermission() {"
start = source.find(start_anchor)
end = source.find(end_anchor, start)
if start < 0 or end < 0 or end <= start:
    raise SystemExit("تعذر تحديد حدود دوال إظهار القفل داخل MonitorService")

source = source[:start] + load_overlay_block().rstrip() + "\n\n" + source[end:]
NATIVE_PATH.write_text(source, encoding="utf-8")
print("تم دمج نافذة القفل التلقائي بطريقة مرنة")
