# Win7 offline runtime toolkit

This toolkit is intentionally implemented with `.cmd` files so it can run on
Windows 7 before the Python/PyInstaller program starts.

## Why this is needed

If `update.exe` reports that `api-ms-win-core-sysinfo-l1-2-0.dll` is missing,
the executable has loaded an app-local UCRT runtime that is too new for
Windows 7. Installing Python will not fix that; the packaged runtime must be
Win7-compatible, and the target machine may also need the VC/UCRT runtime
installed offline.

## Files

- `win7_probe.cmd`: writes `win7_probe_report.txt`.
- `install_win7_runtime.cmd`: installs offline redistributables from `redist`.
- `redist\vc_redist.x64.exe`: optional Microsoft VC runtime installer.
- `redist\*.msu`: optional Windows 7 hotfix packages.

## Recommended flow on the target machine

1. Use the `*_win7_compat.zip` application package, not the normal package.
2. Run `win7_probe.cmd` first.
3. If files or hotfixes are missing, right-click `install_win7_runtime.cmd` and
   choose "Run as administrator".
4. Reboot if any Microsoft runtime package was installed.
5. Run `update.exe` or the main program again.

The installer is offline-only. It does not download anything from the internet.
