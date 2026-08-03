# KidsMonnter Unified Build

This branch consolidates all previous Safe, Smart, and Guard build paths into one official parental-control APK.

The unified build keeps the full protection stack from the source tree:

- Device Admin receiver
- Accessibility uninstall guard
- Overlay lock screen
- Foreground monitoring service
- Boot recovery receiver
- Exact-alarm watchdog
- Device Owner and Lock Task support when the device is provisioned accordingly

Only `apk/KidsMonnter.apk` is published as the official downloadable package.
