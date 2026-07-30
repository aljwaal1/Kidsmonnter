from pathlib import Path

path = Path("native/MainActivityV2.kt")
source = path.read_text(encoding="utf-8")
marker = "UNINSTALL_GUARD_CLASS_ORDER_MARKER"

if marker in source:
    print("Uninstall guard class order already fixed")
    raise SystemExit(0)

start = source.find("class UninstallPinActivity : Activity()")
receiver = source.find("class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()", start)
boot = source.find("class BootReceiver : BroadcastReceiver()", receiver)
if start < 0 or receiver < 0 or boot < 0:
    raise SystemExit("تعذر ترتيب أصناف حارس الحذف")

guard_block = source[start:receiver].rstrip() + "\n\n"
source = source[:start] + source[receiver:]

receiver_line = "class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()\n"
receiver_pos = source.find(receiver_line)
if receiver_pos < 0:
    raise SystemExit("تعذر العثور على مستقبل مسؤول الجهاز")
insert_at = receiver_pos + len(receiver_line)
source = (
    source[:insert_at]
    + "\n// UNINSTALL_GUARD_CLASS_ORDER_MARKER\n"
    + guard_block
    + source[insert_at:]
)
path.write_text(source, encoding="utf-8")
print("Uninstall guard classes moved outside LockActivity contract range")
