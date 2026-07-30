from pathlib import Path

FLUTTER = Path("lib/main.dart")
NATIVE = Path("native/MainActivityV2.kt")
MANIFEST = Path("native/AndroidManifest.xml")
MARKER = "PARENT_PIN_UNINSTALL_GUARD_MARKER"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"تعذر دمج {label}: المقطع المتوقع غير موجود")
    return text.replace(old, new, 1)


flutter = FLUTTER.read_text(encoding="utf-8")
native = NATIVE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER not in native:
    native = replace_once(
        native,
        "import android.app.admin.DevicePolicyManager\n",
        "import android.app.admin.DevicePolicyManager\nimport android.accessibilityservice.AccessibilityService\n",
        "استيراد خدمة إمكانية الوصول",
    )
    native = replace_once(
        native,
        "import android.view.WindowManager\n",
        "import android.view.WindowManager\nimport android.view.accessibility.AccessibilityEvent\n",
        "استيراد أحداث إمكانية الوصول",
    )
    native = replace_once(
        native,
        'private const val MAX_PIN_BLOCK_MS = 60_000L\n',
        'private const val MAX_PIN_BLOCK_MS = 60_000L\n'
        'private const val UNINSTALL_AUTHORIZED_UNTIL_KEY = "uninstall_authorized_until_ms"\n'
        'private const val UNINSTALL_AUTH_WINDOW_MS = 90_000L\n',
        "ثوابت السماح المؤقت بالحذف",
    )

    native = replace_once(
        native,
        '''private fun Context.canUseExactWatchdog(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
        (getSystemService(Context.ALARM_SERVICE) as AlarmManager).canScheduleExactAlarms()
''',
        '''private fun Context.canUseExactWatchdog(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
        (getSystemService(Context.ALARM_SERVICE) as AlarmManager).canScheduleExactAlarms()

// PARENT_PIN_UNINSTALL_GUARD_MARKER
private fun Context.isUninstallGuardAccessibilityEnabled(): Boolean {
    val expected = ComponentName(this, UninstallGuardAccessibilityService::class.java)
        .flattenToString()
    val enabled = Settings.Secure.getString(
        contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
    ).orEmpty()
    return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
}

private fun SharedPreferences.isParentUninstallAuthorized(): Boolean =
    System.currentTimeMillis() <= getLong(UNINSTALL_AUTHORIZED_UNTIL_KEY, 0L)
''',
        "التحقق من حارس الحذف",
    )

    old_prepare = '''private fun Activity.prepareParentAuthorizedUninstall(prefs: SharedPreferences): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    val admin = deviceAdminComponent()
    if (!manager.isDeviceOwnerApp(packageName)) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_REJECTED", "reason=device_owner_required")
        return false
    }

    return try {
        prefs.edit()
            .putBoolean("enabled", false)
            .remove(LAST_TICK_KEY)
            .remove("unlocked_date")
            .commit()
        syncBootProtectionState(false)
        stopService(Intent(this, MonitorService::class.java))

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            manager.setStatusBarDisabled(admin, false)
        }
        manager.setLockTaskPackages(admin, emptyArray<String>())
        manager.setUninstallBlocked(admin, packageName, false)
        appendGuardLog("UNINSTALL_AUTHORIZED_BY_PARENT_PIN", "deviceOwner=true")

        @Suppress("DEPRECATION")
        manager.clearDeviceOwnerApp(packageName)
        appendGuardLog("DEVICE_OWNER_CLEARED_FOR_UNINSTALL")
        true
    } catch (error: Exception) {
        appendGuardLog("UNINSTALL_AUTHORIZATION_FAILED", error = error)
        false
    }
}
'''
    new_prepare = '''private fun Activity.prepareParentAuthorizedUninstall(prefs: SharedPreferences): Boolean {
    val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    val admin = deviceAdminComponent()
    return try {
        prefs.edit()
            .putBoolean("enabled", false)
            .putLong(
                UNINSTALL_AUTHORIZED_UNTIL_KEY,
                System.currentTimeMillis() + UNINSTALL_AUTH_WINDOW_MS,
            )
            .remove(LAST_TICK_KEY)
            .remove("unlocked_date")
            .commit()
        syncBootProtectionState(false)
        stopService(Intent(this, MonitorService::class.java))

        if (manager.isDeviceOwnerApp(packageName)) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                manager.setStatusBarDisabled(admin, false)
            }
            manager.setLockTaskPackages(admin, emptyArray<String>())
            manager.setUninstallBlocked(admin, packageName, false)
            @Suppress("DEPRECATION")
            manager.clearDeviceOwnerApp(packageName)
            appendGuardLog("UNINSTALL_AUTHORIZED_BY_PARENT_PIN", "mode=device_owner")
        } else {
            if (manager.isAdminActive(admin)) manager.removeActiveAdmin(admin)
            appendGuardLog("UNINSTALL_AUTHORIZED_BY_PARENT_PIN", "mode=device_admin")
        }
        true
    } catch (error: Exception) {
        prefs.edit().remove(UNINSTALL_AUTHORIZED_UNTIL_KEY).apply()
        appendGuardLog("UNINSTALL_AUTHORIZATION_FAILED", error = error)
        false
    }
}
'''
    native = replace_once(native, old_prepare, new_prepare, "السماح بالحذف بعد رمز الأب")

    old_authorize = '''                    } else {
                        val manager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                        if (!manager.isDeviceOwnerApp(packageName)) {
                            result.error(
                                "DEVICE_OWNER_REQUIRED",
                                "منع الحذف الكامل يحتاج تفعيل Device Owner أولاً",
                                null,
                            )
                        } else if (!prepareParentAuthorizedUninstall(prefs)) {
                            result.error(
                                "UNINSTALL_PREPARE_FAILED",
                                "تعذر إلغاء حماية الحذف بصورة آمنة",
                                null,
                            )
                        } else {
'''
    new_authorize = '''                    } else {
                        if (!prepareParentAuthorizedUninstall(prefs)) {
                            result.error(
                                "UNINSTALL_PREPARE_FAILED",
                                "تعذر إلغاء حماية الحذف بصورة آمنة",
                                null,
                            )
                        } else {
'''
    native = replace_once(native, old_authorize, new_authorize, "إزالة اشتراط Device Owner للحذف المصرح")

    native = replace_once(
        native,
        '                    if (!dpm.isAdminActive(admin)) missing.add("device_admin")\n'
        '                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")\n',
        '                    if (!dpm.isAdminActive(admin)) missing.add("device_admin")\n'
        '                    if (!isUninstallGuardAccessibilityEnabled()) missing.add("uninstall_guard")\n'
        '                    if (!Settings.canDrawOverlays(this)) missing.add("overlay")\n',
        "اشتراط حارس الحذف قبل بدء الحماية",
    )

    native = replace_once(
        native,
        '''                "openOverlaySettings" -> {
''',
        '''                "openAccessibilitySettings" -> {
                    startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                    result.success(true)
                }
                "openOverlaySettings" -> {
''',
        "قناة فتح إعدادات إمكانية الوصول",
    )

    native = replace_once(
        native,
        '                        "batteryOptimizationIgnored" to isIgnoringBatteryOptimizations()\n',
        '                        "batteryOptimizationIgnored" to isIgnoringBatteryOptimizations(),\n'
        '                        "uninstallGuardEnabled" to isUninstallGuardAccessibilityEnabled()\n',
        "إرجاع حالة حارس الحذف",
    )

    guard_classes = r'''class UninstallPinActivity : Activity() {
    private val prefs by lazy { guardPrefs() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        val pin = EditText(this).apply {
            hint = "رمز الأب من 6 أرقام"
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            maxLines = 1
        }
        val status = TextView(this).apply {
            gravity = Gravity.CENTER
            setTextColor(Color.RED)
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(42, 42, 42, 42)
            addView(TextView(this@UninstallPinActivity).apply {
                text = "لا يمكن حذف التطبيق دون رمز الأب"
                textSize = 24f
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, -2))
            addView(pin, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 24 })
            addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })
            addView(Button(this@UninstallPinActivity).apply {
                text = "السماح بالحذف"
                setOnClickListener {
                    val candidate = pin.text.toString().trim()
                    if (!verifyPin(prefs, candidate)) {
                        recordFailedAttempt(
                            this@UninstallPinActivity,
                            prefs,
                            "محاولة حذف التطبيق دون رمز صحيح",
                        )
                        status.text = "رمز الأب غير صحيح"
                        pin.text.clear()
                    } else if (!prepareParentAuthorizedUninstall(prefs)) {
                        status.text = "تعذر تجهيز الحذف بصورة آمنة"
                    } else {
                        openSelfUninstallScreen()
                        finish()
                    }
                }
            }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 18 })
            addView(Button(this@UninstallPinActivity).apply {
                text = "رجوع"
                setOnClickListener { finish() }
            }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10 })
        }
        setContentView(root)
    }
}

class UninstallGuardAccessibilityService : AccessibilityService() {
    private val protectedPackages = setOf(
        "com.android.settings",
        "com.android.packageinstaller",
        "com.google.android.packageinstaller",
        "com.android.permissioncontroller",
        "com.google.android.permissioncontroller",
    )

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return
        val prefs = guardPrefs()
        if (!hasStoredPin(prefs) || prefs.isParentUninstallAuthorized()) return

        val sourcePackage = event.packageName?.toString().orEmpty()
        if (sourcePackage !in protectedPackages) return

        val className = event.className?.toString().orEmpty()
        val visibleText = buildString {
            append(event.text.joinToString(" "))
            append(' ')
            append(event.contentDescription?.toString().orEmpty())
        }
        val mentionsThisApp = visibleText.contains("حارس وقت الأطفال", ignoreCase = true) ||
            visibleText.contains("KidsMonnter", ignoreCase = true) ||
            visibleText.contains(packageName, ignoreCase = true)
        val sensitiveClass = listOf(
            "UninstallerActivity",
            "UninstallActivity",
            "InstalledAppDetails",
            "DeviceAdminSettings",
            "DeviceAdminAdd",
            "ManageApplications",
        ).any { className.contains(it, ignoreCase = true) }
        val deviceAdminScreen = className.contains("DeviceAdmin", ignoreCase = true)

        if (!mentionsThisApp && !deviceAdminScreen && !sensitiveClass) return
        performGlobalAction(GLOBAL_ACTION_BACK)
        try {
            startActivity(
                Intent(this, UninstallPinActivity::class.java).addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP,
                ),
            )
            appendGuardLog(
                "UNINSTALL_ATTEMPT_INTERCEPTED",
                "package=$sourcePackage class=$className",
            )
        } catch (error: Exception) {
            appendGuardLog("UNINSTALL_GUARD_LAUNCH_FAILED", error = error)
        }
    }

    override fun onInterrupt() = Unit
}

'''
    native = replace_once(
        native,
        "class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()",
        guard_classes + "class KidsMonnterDeviceAdminReceiver : DeviceAdminReceiver()",
        "أنشطة وخدمة حارس الحذف",
    )

if MARKER not in flutter:
    flutter = replace_once(
        flutter,
        "  bool _batteryOptimizationIgnored = false;\n",
        "  bool _batteryOptimizationIgnored = false;\n  bool _uninstallGuardEnabled = false;\n",
        "حالة حارس الحذف في الواجهة",
    )
    flutter = replace_once(
        flutter,
        "        _batteryOptimizationIgnored = map['batteryOptimizationIgnored'] == true;\n",
        "        _batteryOptimizationIgnored = map['batteryOptimizationIgnored'] == true;\n"
        "        _uninstallGuardEnabled = map['uninstallGuardEnabled'] == true;\n",
        "قراءة حالة حارس الحذف",
    )
    flutter = replace_once(
        flutter,
        "      _batteryOptimizationIgnored &&\n      _devicePolicy.adminActive; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER",
        "      _batteryOptimizationIgnored &&\n"
        "      _uninstallGuardEnabled &&\n"
        "      _devicePolicy.adminActive; // MANDATORY_DEVICE_ADMIN_PROTECTION_MARKER\n"
        "  // PARENT_PIN_UNINSTALL_GUARD_MARKER",
        "اشتراط حارس الحذف في الجاهزية",
    )
    card_anchor = '''            const SizedBox(height: 10),
            item(
              ready: status.overlayAllowed,
'''
    card_replacement = '''            const SizedBox(height: 10),
            item(
              ready: _uninstallGuardEnabled,
              title: 'قفل الحذف برمز الأب',
              subtitle: _uninstallGuardEnabled
                  ? 'مفعّل: تتم مقاطعة شاشة حذف التطبيق ويُطلب رمز الأب.'
                  : 'إجباري: فعّل خدمة حارس وقت الأطفال ضمن إمكانية الوصول.',
              action: () => _openRequiredSetting('openAccessibilitySettings'),
              button: 'تفعيل حارس الحذف',
            ),
            const SizedBox(height: 10),
            item(
              ready: status.overlayAllowed,
'''
    flutter = replace_once(flutter, card_anchor, card_replacement, "بطاقة حارس الحذف")

if MARKER not in manifest:
    manifest = replace_once(
        manifest,
        '''        <service
            android:name=".MonitorService"
''',
        '''        <!-- PARENT_PIN_UNINSTALL_GUARD_MARKER -->
        <activity
            android:name=".UninstallPinActivity"
            android:excludeFromRecents="true"
            android:exported="false"
            android:launchMode="singleTask"
            android:screenOrientation="portrait"
            android:theme="@style/LaunchTheme" />

        <service
            android:name=".UninstallGuardAccessibilityService"
            android:enabled="true"
            android:exported="false"
            android:label="حارس حذف التطبيق"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/uninstall_guard_accessibility" />
        </service>

        <service
            android:name=".MonitorService"
''',
        "تعريف حارس الحذف في Manifest",
    )

FLUTTER.write_text(flutter, encoding="utf-8")
NATIVE.write_text(native, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
print("Parent-PIN uninstall guard merged")
