from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if old not in text:
        raise SystemExit(f"Expected source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


main_path = Path("lib/main.dart")
native_path = Path("native/MainActivityV2.kt")

replace_once(
    main_path,
    """    required this.lockTaskPermitted,\n  });\n\n  final bool deviceOwner;\n  final bool adminActive;\n  final bool lockTaskPermitted;\n\n  factory DevicePolicyStatus.fromMap(Map<String, dynamic>? map) {\n    return DevicePolicyStatus(\n      deviceOwner: map?['deviceOwner'] == true,\n      adminActive: map?['adminActive'] == true,\n      lockTaskPermitted: map?['lockTaskPermitted'] == true,\n    );\n  }\n\n  bool get uninstallProtectionActive => deviceOwner;\n""",
    """    required this.lockTaskPermitted,\n    required this.uninstallBlocked,\n  });\n\n  final bool deviceOwner;\n  final bool adminActive;\n  final bool lockTaskPermitted;\n  final bool uninstallBlocked;\n\n  factory DevicePolicyStatus.fromMap(Map<String, dynamic>? map) {\n    return DevicePolicyStatus(\n      deviceOwner: map?['deviceOwner'] == true,\n      adminActive: map?['adminActive'] == true,\n      lockTaskPermitted: map?['lockTaskPermitted'] == true,\n      uninstallBlocked: map?['uninstallBlocked'] == true,\n    );\n  }\n\n  bool get uninstallProtectionActive =>\n      deviceOwner && adminActive && uninstallBlocked;\n""",
    "final bool uninstallBlocked;",
)

replace_once(
    main_path,
    """    lockTaskPermitted: false,\n  );\n""",
    """    lockTaskPermitted: false,\n    uninstallBlocked: false,\n  );\n""",
    "uninstallBlocked: false,",
)

replace_once(
    native_path,
    """                \"getDevicePolicyStatus\" -> {\n                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager\n                    result.success(mapOf(\n                        \"deviceOwner\" to dpm.isDeviceOwnerApp(packageName),\n                        \"adminActive\" to dpm.isAdminActive(deviceAdminComponent()),\n                        \"lockTaskPermitted\" to dpm.isLockTaskPermitted(packageName)\n                    ))\n                }\n""",
    """                \"getDevicePolicyStatus\" -> {\n                    val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager\n                    val admin = deviceAdminComponent()\n                    val deviceOwner = dpm.isDeviceOwnerApp(packageName)\n                    val uninstallBlocked = if (deviceOwner) {\n                        try {\n                            dpm.isUninstallBlocked(admin, packageName)\n                        } catch (_: SecurityException) {\n                            false\n                        }\n                    } else {\n                        false\n                    }\n                    result.success(mapOf(\n                        \"deviceOwner\" to deviceOwner,\n                        \"adminActive\" to dpm.isAdminActive(admin),\n                        \"lockTaskPermitted\" to dpm.isLockTaskPermitted(packageName),\n                        \"uninstallBlocked\" to uninstallBlocked\n                    ))\n                }\n""",
    '"uninstallBlocked" to uninstallBlocked',
)

print("Preflight hardening merged successfully.")
