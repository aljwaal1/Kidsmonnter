# KidsMonnter — Progress Run 08

## النطاق

مراجعة طبقة تشخيص جاهزية الحماية وإجراء المعالجة المرتبط بكل حالة، دون تعديل خدمة Android أو شاشة القفل أو Manifest أو تخزين PIN أو احتساب وقت الاستخدام.

## ما تمت مراجعته

- `lib/guard_diagnostics.dart`
- `lib/guard_diagnostics_presentation.dart`
- `lib/guard_diagnostics_card.dart`
- `test/guard_diagnostics_card_test.dart`
- حالات الجاهزية التي تنتج عن نبض الخدمة وصلاحية Overlay.

## المشكلة المكتشفة

كانت بطاقة التشخيص تعرض زرًا عامًا باسم «معالجة المشكلة» دون تحديد الإجراء المناسب. هذا يجعل ربط البطاقة بالشاشة الرئيسية غير آمن، لأن نقص Overlay يحتاج فتح إعدادات الصلاحية، بينما قدم نبض الخدمة يحتاج إعادة تشغيل الخدمة، وحالة بدء الخدمة تحتاج إعادة فحص فقط.

## التغيير

- إضافة `GuardDiagnosticAction` كعقد واضح للإجراءات الممكنة.
- إضافة `GuardDiagnosticActionResolver` لتحويل كل حالة جاهزية إلى إجراء واحد محدد.
- تحديث بطاقة التشخيص لتعرض تسمية وأيقونة مناسبة للإجراء.
- تمرير نوع الإجراء إلى المستدعي بدل تنفيذ Callback عام غير محدد.

## التوجيه الحالي

- `disabled` و`ready`: لا يوجد إجراء.
- `starting`: إعادة فحص الحالة.
- `overlayMissing`: فتح إعدادات Overlay.
- `serviceStale`: إعادة تشغيل خدمة الحماية.

## الاختبارات

تم تحديث اختبارات Widget للتحقق من:

- عدم ظهور زر عند الجاهزية الكاملة.
- تمرير `openOverlaySettings` عند نقص Overlay.
- تمرير `restartProtectionService` عند قدم نبض الخدمة.
- تمرير `refreshStatus` أثناء انتظار أول نبضة.

## ما لم يتغير

- `MonitorService`
- `LockActivity`
- `AndroidManifest.xml`
- PIN
- عداد الاستخدام
- الشاشة الرئيسية

## الخطوة التالية

ربط `serviceHeartbeatMs` داخل `GuardStatus`، ثم إدراج `GuardDiagnosticsCard` في الشاشة الرئيسية وربط الإجراءات الثلاثة بقنوات Android الفعلية بعد تأكيد نجاح التحليل والاختبارات والبناء.
