import 'package:flutter/material.dart';

import 'guard_diagnostics.dart';
import 'guard_diagnostics_action.dart';
import 'guard_diagnostics_presentation.dart';

class GuardDiagnosticsCard extends StatelessWidget {
  const GuardDiagnosticsCard({
    required this.diagnostics,
    required this.now,
    this.onResolveIssue,
    super.key,
  });

  final GuardDiagnostics diagnostics;
  final DateTime now;
  final ValueChanged<GuardDiagnosticAction>? onResolveIssue;

  @override
  Widget build(BuildContext context) {
    final readiness = diagnostics.readinessAt(now);
    final presentation = GuardDiagnosticPresentation.fromReadiness(
      readiness,
      heartbeatAge: diagnostics.heartbeatAgeAt(now),
    );
    final action = GuardDiagnosticActionResolver.forReadiness(readiness);
    final visual = _visualFor(context, presentation.tone);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(visual.icon, color: visual.color, size: 30),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    presentation.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: visual.color,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(presentation.message),
                  if (action != GuardDiagnosticAction.none &&
                      onResolveIssue != null) ...[
                    const SizedBox(height: 12),
                    FilledButton.tonalIcon(
                      onPressed: () => onResolveIssue!(action),
                      icon: Icon(_iconForAction(action)),
                      label: Text(
                        GuardDiagnosticActionResolver.labelFor(action),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _iconForAction(GuardDiagnosticAction action) {
    switch (action) {
      case GuardDiagnosticAction.none:
        return Icons.check_circle_outline;
      case GuardDiagnosticAction.refreshStatus:
        return Icons.refresh;
      case GuardDiagnosticAction.openOverlaySettings:
        return Icons.layers_outlined;
      case GuardDiagnosticAction.restartProtectionService:
        return Icons.restart_alt;
    }
  }

  _DiagnosticVisual _visualFor(
    BuildContext context,
    GuardDiagnosticTone tone,
  ) {
    final scheme = Theme.of(context).colorScheme;
    switch (tone) {
      case GuardDiagnosticTone.neutral:
        return _DiagnosticVisual(Icons.shield_outlined, scheme.outline);
      case GuardDiagnosticTone.success:
        return _DiagnosticVisual(Icons.verified_user_outlined, scheme.primary);
      case GuardDiagnosticTone.warning:
        return _DiagnosticVisual(Icons.warning_amber_rounded, scheme.tertiary);
      case GuardDiagnosticTone.danger:
        return _DiagnosticVisual(Icons.error_outline, scheme.error);
    }
  }
}

class _DiagnosticVisual {
  const _DiagnosticVisual(this.icon, this.color);

  final IconData icon;
  final Color color;
}
