from pathlib import Path

NATIVE = Path("native/MainActivityV2.kt")
MANIFEST = Path("native/AndroidManifest.xml")
ACCESSIBILITY_FILES = (
    Path("native/res/xml/uninstall_guard_accessibility.xml"),
    Path("android/app/src/main/res/xml/uninstall_guard_accessibility.xml"),
)
MARKER = "PARENT_PIN_FORCE_STOP_GUARD_MARKER"

native = NATIVE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

if MARKER not in native:
    native = native.replace(
        "import android.view.accessibility.AccessibilityEvent\n",
        "import android.view.accessibility.AccessibilityEvent\n"
        "import android.view.accessibility.AccessibilityNodeInfo\n",
        1,
    )
    native = native.replace(
        'private const val UNINSTALL_AUTH_WINDOW_MS = 90_000L\n',
        'private const val UNINSTALL_AUTH_WINDOW_MS = 90_000L\n'
        'private const val SETTINGS_AUTHORIZED_UNTIL_ELAPSED_KEY = "settings_authorized_until_elapsed_ms"\n'
        'private const val SETTINGS_AUTH_WINDOW_MS = 90_000L\n',
        1,
    )
    native = native.replace(
        '''private fun SharedPreferences.isParentUninstallAuthorized(): Boolean =
    System.currentTimeMillis() <= getLong(UNINSTALL_AUTHORIZED_UNTIL_KEY, 0L)
''',
        '''private fun SharedPreferences.isParentUninstallAuthorized(): Boolean =
    System.currentTimeMillis() <= getLong(UNINSTALL_AUTHORIZED_UNTIL_KEY, 0L)

// PARENT_PIN_FORCE_STOP_GUARD_MARKER
private fun SharedPreferences.isParentAppSettingsAuthorized(): Boolean {
    val now = SystemClock.elapsedRealtime()
    val until = getLong(SETTINGS_AUTHORIZED_UNTIL_ELAPSED_KEY, 0L)
    return until >= now && until - now <= SETTINGS_AUTH_WINDOW_MS
}

private fun SharedPreferences.authorizeParentAppSettings(): Boolean =
    edit().putLong(
        SETTINGS_AUTHORIZED_UNTIL_ELAPSED_KEY,
        SystemClock.elapsedRealtime() + SETTINGS_AUTH_WINDOW_MS,
    ).commit()
''',
        1,
    )

    service_start = native.find("class UninstallGuardAccessibilityService : AccessibilityService()")
    if service_start < 0:
        raise SystemExit("تعذر العثور على خدمة حارس الحذف")
    service_end_marker = "    override fun onInterrupt() = Unit\n}"
    service_end = native.find(service_end_marker, service_start)
    if service_end < 0:
        raise SystemExit("تعذر تحديد نهاية خدمة حارس الحذف")
    service_end += len(service_end_marker)

    replacement = r'''class ForceStopPinActivity : Activity() {
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
            addView(TextView(this@ForceStopPinActivity).apply {
                text = "إدارة KidsMonnter محمية برمز الأب"
                textSize = 24f
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, -2))
            addView(TextView(this@ForceStopPinActivity).apply {
                text = "يلزم رمز الأب قبل فتح صفحة الإيقاف الإجباري أو إزالة الحماية."
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })
            addView(pin, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 24 })
            addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12 })
            addView(Button(this@ForceStopPinActivity).apply {
                text = "السماح بإدارة التطبيق"
                setOnClickListener {
                    val remaining = lockPinBlockRemainingMs(prefs)
                    if (remaining > 0L) {
                        status.text = lockDelayText(remaining)
                        return@setOnClickListener
                    }
                    val candidate = pin.text.toString().trim()
                    if (!verifyPin(prefs, candidate)) {
                        val delay = registerLockPinFailure(
                            this@ForceStopPinActivity,
                            prefs,
                            "محاولة فتح الإيقاف الإجباري دون رمز صحيح",
                        )
                        status.text = "رمز الأب غير صحيح. ${lockDelayText(delay)}"
                        pin.text.clear()
                        return@setOnClickListener
                    }
                    clearLockPinFailureState(prefs)
                    if (!prefs.authorizeParentAppSettings()) {
                        status.text = "تعذر حفظ السماح المؤقت. حاول مرة أخرى."
                        return@setOnClickListener
                    }
                    appendGuardLog("APP_SETTINGS_AUTHORIZED_BY_PARENT_PIN", "windowMs=$SETTINGS_AUTH_WINDOW_MS")
                    startActivity(
                        Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.parse("package:$packageName"),
                        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                    )
                    finish()
                }
            }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 18 })
            addView(Button(this@ForceStopPinActivity).apply {
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
        "com.huawei.systemmanager",
    )
    private var lastGateLaunchElapsedMs = 0L

    private fun collectVisibleText(root: AccessibilityNodeInfo?): String {
        root ?: return ""
        val output = StringBuilder()
        fun visit(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > 18 || output.length > 12000) return
            node.text?.toString()?.takeIf { it.isNotBlank() }?.let {
                output.append(' ').append(it)
            }
            node.contentDescription?.toString()?.takeIf { it.isNotBlank() }?.let {
                output.append(' ').append(it)
            }
            for (index in 0 until node.childCount) visit(node.getChild(index), depth + 1)
        }
        visit(root, 0)
        return output.toString()
    }

    private fun textMentionsKidsMonnter(text: String): Boolean =
        text.contains("حارس وقت الأطفال", ignoreCase = true) ||
            text.contains("KidsMonnter", ignoreCase = true) ||
            text.contains(packageName, ignoreCase = true)

    private fun launchParentGate(activityClass: Class<out Activity>, eventName: String, details: String) {
        val now = SystemClock.elapsedRealtime()
        if (now - lastGateLaunchElapsedMs < 1200L) return
        lastGateLaunchElapsedMs = now
        performGlobalAction(GLOBAL_ACTION_BACK)
        try {
            startActivity(
                Intent(this, activityClass).addFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP,
                ),
            )
            appendGuardLog(eventName, details)
        } catch (error: Exception) {
            appendGuardLog("PARENT_SECURITY_GATE_LAUNCH_FAILED", details, error)
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return
        val prefs = guardPrefs()
        if (!hasStoredPin(prefs)) return

        val sourcePackage = event.packageName?.toString().orEmpty()
        if (sourcePackage !in protectedPackages) return

        val className = event.className?.toString().orEmpty()
        val eventText = buildString {
            append(event.text.joinToString(" "))
            append(' ')
            append(event.contentDescription?.toString().orEmpty())
        }
        val rootText = collectVisibleText(rootInActiveWindow)
        val visibleText = "$eventText $rootText"
        val mentionsThisApp = textMentionsKidsMonnter(visibleText)
        if (!mentionsThisApp) return

        val appDetailsScreen = listOf(
            "InstalledAppDetails",
            "AppInfo",
            "AppDetails",
            "ApplicationInfo",
        ).any { className.contains(it, ignoreCase = true) }
        val forceStopText = listOf(
            "force stop",
            "force-stop",
            "إيقاف إجباري",
            "فرض الإيقاف",
            "ايقاف اجباري",
            "إيقاف بالقوة",
        ).any { visibleText.contains(it, ignoreCase = true) }
        val uninstallScreen = listOf(
            "UninstallerActivity",
            "UninstallActivity",
            "PackageInstallerActivity",
        ).any { className.contains(it, ignoreCase = true) } ||
            listOf("uninstall", "إلغاء التثبيت", "ازالة التطبيق", "إزالة التطبيق")
                .any { visibleText.contains(it, ignoreCase = true) }
        val destructiveAdminScreen = className.contains("DeviceAdmin", ignoreCase = true) &&
            listOf("deactivate", "disable", "إلغاء التنشيط", "تعطيل")
                .any { visibleText.contains(it, ignoreCase = true) }

        if (prefs.isParentAppSettingsAuthorized()) return
        if (uninstallScreen && !prefs.isParentUninstallAuthorized()) {
            launchParentGate(
                UninstallPinActivity::class.java,
                "UNINSTALL_ATTEMPT_INTERCEPTED",
                "package=$sourcePackage class=$className",
            )
            return
        }
        if (appDetailsScreen || forceStopText || destructiveAdminScreen) {
            launchParentGate(
                ForceStopPinActivity::class.java,
                "FORCE_STOP_OR_APP_SETTINGS_INTERCEPTED",
                "package=$sourcePackage class=$className forceStop=$forceStopText",
            )
        }
    }

    override fun onInterrupt() = Unit
}'''

    native = native[:service_start] + replacement + native[service_end:]

if MARKER not in manifest:
    anchor = '''        <activity
            android:name=".UninstallPinActivity"
'''
    addition = '''        <!-- PARENT_PIN_FORCE_STOP_GUARD_MARKER -->
        <activity
            android:name=".ForceStopPinActivity"
            android:excludeFromRecents="true"
            android:exported="false"
            android:launchMode="singleTask"
            android:screenOrientation="portrait"
            android:theme="@style/LaunchTheme" />

        <activity
            android:name=".UninstallPinActivity"
'''
    if anchor not in manifest:
        raise SystemExit("تعذر إضافة شاشة رمز الأب للإيقاف الإجباري")
    manifest = manifest.replace(anchor, addition, 1)

for path in ACCESSIBILITY_FILES:
    if not path.exists():
        continue
    xml = path.read_text(encoding="utf-8")
    xml = xml.replace(
        'android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"',
        'android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged|typeViewClicked"',
    )
    path.write_text(xml, encoding="utf-8")

NATIVE.write_text(native, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
print("Parent-PIN force-stop guard merged")
