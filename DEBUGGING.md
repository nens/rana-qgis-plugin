# Debugging tips & Tricks

## Printing in plugins

`print` statements are not visible in the UI, instead you need to use `QgsMessageLog.logMessage` which will send the messages to the logging panel in QGIS., E.g.

```python
from qgis.core import Qgis, QgsMessageLog
    
QgsMessageLog.logMessage('foo', "Rana", Qgis.MessageLevel.Info)
```

will show `TIMESTAMP     INFO    foo` in the Rana tab of the logging panel.

> [!NOTE]
> `logMessage` can only take strings so you must format anything to a string before passing it.

> [!TIP]
> The `UICommunication` module has `log_info`, `log_warn` and `log_err` functions as shortcuts that only need the message as argument and will set the correct mode and send it to the correct context (Rana).


## Running QGIS in debug mode (linux)

Using `'QGIS_DEBUG=1 QT_LOGGING_RULES="*.debug=true" qgis'` to start QGIS will enable debug logging and print it to the console. 


## Obtaining and processing crash dumps

Full on QGIS crashes are hard to debug because you typically get no or minimal information. A crash dump can provide valuable information for debugging.

## Windows

### Prerequisites

#### ProcDump

ProcDump (part of Microsoft's Sysinternals tools). You can download it from https://learn.microsoft.com/en-us/sysinternals/downloads/procdump and then unzip the zip and directly use the executable.

Alternatively, you can install it with Windows Package Manager:

```powershell
winget install Microsoft.Sysinternals.ProcDump
```


#### CDB

The dump can be inspected with an application like CDB. To install download the the [Windows SDK](https://developer.microsoft.com/windows/downloads/windows-sdk/) and select only **Debugging Tools for Windows** in the feature selection
screen. CDB is normally installed under:

```text
C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe
```


### Capture a dump with ProcDump


1. Open Task Manager and use the **Details** tab to confirm QGIS's process name. It is commonly `qgis-bin.exe`, but the name can differ by QGIS installation.
2. Open PowerShell in the directory containing `procdump.exe`.
3. Start ProcDump before reproducing the crash:

   ```powershell
   .\procdump.exe -ma -e -w qgis-bin.exe
   ```

   The options mean:

   - `-ma`: write a full user-mode dump;
   - `-e`: capture an unhandled exception;
   - `-w`: wait for the named process if QGIS is not running yet.

4. Reproduce the crash in QGIS.
5. ProcDump writes a `.dmp` file in its working directory. The dump may be large; do not send it to an AI service directly.

If QGIS is already running and you do not want ProcDump to wait for a new process, omit `-w` and provide the process ID instead:

```powershell
.\procdump.exe -ma -e <process-id> qgis-crash.dmp
```

### Produce a text report with CDB

PowerShell must use the `&` call operator when executing a quoted path:

```powershell
& 'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe' `
  -z .\qgis-bin.exe_YYYYMMDD_HHMMSS.dmp `
  -c ".symfix; .reload; !analyze -v; ~*kb; lm; q" > analysis.txt
```

If symbols are unavailable, use this shorter command:

```powershell
& 'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe' `
  -z .\qgis-bin.exe_YYYYMMDD_HHMMSS.dmp `
  -c "!analyze -v; ~*kb; lm; q" > analysis.txt
```

Inspect or share `analysis.txt` rather than the dump. The text report is normally much smaller and can be reviewed without transferring the dump's memory contents.

## Linux

> [!NOTE]
> This part of the guide is untested!


Linux uses core dumps. Start QGIS from a shell where core  dumps are enabled:

```bash
ulimit -c unlimited
QGIS_DEBUG=1 QT_LOGGING_RULES='*.debug=true' qgis 2>&1 | tee qgis.log
```

On distributions using `systemd-coredump`, list captured crashes with:

```bash
coredumpctl list qgis
```

Show metadata for the latest crash:

```bash
coredumpctl info qgis
```

Open the latest dump in GDB:

```bash
coredumpctl debug qgis
```

At the GDB prompt, generate a compact all-thread report:

```gdb
set pagination off
set logging file analysis.txt
set logging overwrite on
set logging on
thread apply all bt
info registers
info sharedlibrary
set logging off
quit
```

`thread apply all bt` is the Linux equivalent of WinDbg's `~*kb`. It reports the native stack of every thread, which is important for diagnosing races and thread-affinity problems. If the system does not use `systemd-coredump`, locate the core file according to the system's core-dump configuration and run GDB directly:

```bash
gdb -q /path/to/qgis /path/to/core
```

Then use the same GDB commands above. Do not use `coredumpctl dump` unless you intend to copy the complete core file; it can be very large.
