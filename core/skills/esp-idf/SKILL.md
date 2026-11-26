---
name: esp-idf
description: Builds, flashes, monitors, and debugs Espressif boards (ESP32, ESP32-S3, ESP32-C3, ESP32-C6, and other Espressif chips) with pure ESP-IDF on macOS, not Arduino or PlatformIO. Use whenever the user mentions ESP32, ESP-IDF, idf.py, esptool, sdkconfig, Kconfig, FreeRTOS on an Espressif chip, flashing a board, a serial port, a panic or Guru Meditation backtrace, idf_component.yml or a registry component, clangd or VS Code errors in an IDF project, or firmware for an Espressif chip.
compatibility: Claude Code on macOS with Homebrew, git, and Python 3. ESP-IDF itself is installed per setup-macos.md; a board on a USB serial port is needed to flash or monitor.
---

# ESP-IDF on this Mac

Global skill: the workflow, the toolchain pin and the limits around the board. Project facts (chip, board, pin map, layout, secrets header) come from the repo: its `CLAUDE.md`, design notes and `sdkconfig.defaults`. When a fact the task needs is in none of them, ask the user rather than assume it: a wrong chip or port lands on real hardware. `${CLAUDE_SKILL_DIR}` is this file's directory.

| File | Use |
|---|---|
| `idf-version` | Read. The pinned ESP-IDF tag, the only authoritative copy. |
| `setup-macos.md` | Read only when installing or bumping the toolchain. |
| `scripts/check_toolchain.sh` | Run. Read-only: install against the pin, installed chips and debuggers, `export.sh`, boards on USB. |
| `scripts/serial_tail.py` | Run. Bounded serial reader that replaces `idf.py monitor` in tool calls (step 5). |
| `references/ports.md` | Read when a port is ambiguous, missing or busy. |
| `references/debugging.md` | Read to decode a panic, for the reader's full flags, or before using esp-idf-monitor's scripted mode. |
| `references/project-layout.md` | Read when creating a project, adding a dependency, overriding a component, or writing code in a project with no style of its own. |
| `references/editor-clangd.md` | Read for clangd, VS Code, IntelliSense or editor errors. |

## Fixed decisions

- **Pure ESP-IDF.** No Arduino core, PlatformIO or pioarduino. C by default; C++ only where a library forces it, behind one wrapper that exposes `extern "C"` functions. An Arduino-only library comes in as an IDF component; the build system stays IDF.
- **One toolchain per machine**: `~/esp/esp-idf` at the tag in `idf-version`, tools in `~/.espressif/`, shared by every project here. A bump is a deliberate change (edit `idf-version`, follow the bump step in `setup-macos.md`, rebuild every project), not a fix for one build error.
- **The chip comes from the project**: its docs or `sdkconfig.defaults`. If nothing says, ask.
- **Toolchain changes change the machine** (Homebrew packages, a large download, the IDF venv; esp-clang, a RISC-V gdb and a newer esp-idf-monitor count too). Make them only when the user asks in that message, following `setup-macos.md`; otherwise report what `check_toolchain.sh` says. The IDF venv belongs to `install.sh`, so packages go in through it, not `pip install`.
- **eFuses are one-way.** Never run `idf.py efuse-*` or an `espefuse` burn, protect or set-flash-voltage command, and never put `CONFIG_SECURE_BOOT*`, `CONFIG_SECURE_FLASH_ENC*`, another key from the step-4 grep, or any key whose Kconfig help says it burns or sets an eFuse into `sdkconfig.defaults`, unless the user has answered yes to an explicit "this permanently burns eFuses on <board>, proceed?". A flash request does not cover a build that burns eFuses on boot.

## Procedure

### 0. Environment, every command

Shell state does not carry between Bash calls, so every call that runs `idf.py` or `serial_tail.py` sources the export script (silenced: it prints on both streams), and every `idf.py` names the project with `-C "<dir>"`, its absolute path. `-C` also ties a flash to the project whose board you resolved, not to whatever app the shell sits in. A failed activation shows up as `command not found`; `check_toolchain.sh` says why.

```bash
. "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 && idf.py -C "<dir>" build
```

Never run from a tool call, alone or chained: `idf.py menuconfig | monitor | gdb | gdbtui | gdbgui | openocd | confserver`. They wait on a terminal or run until killed, and `idf.py flash monitor` flashes before it hangs. Step 2 replaces `menuconfig`, step 5 replaces `monitor`.

Once per session, before the first `idf.py`:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/check_toolchain.sh"
```

Exit 0: go. Exit 1 (not installed, tools missing, `export.sh` fails, or the pin file is missing): stop, quote its output, offer `setup-macos.md`. A tag that differs from the pin is a warning, not a stop; report it and leave the checkout alone, since switching it is a toolchain change. Its `targets:` line lists the installed chips, `gdb:` the debuggers, `boards:` the ports with their USB vendor.

### 1. Find the board

For flash, monitor and reset only; skip it for build, configure, size and fixes. Ports are `/dev/cu.*`; `/dev/tty.*` blocks on open. Resolve in this order:

1. The project's `## Boards` section, one `<board name>: /dev/cu.…` line per board, in `CLAUDE.md` or `CLAUDE.local.md` of `<dir>` or the repo root. Read it explicitly, since those files load only when `<dir>` is under the session's directory (the `awk` drops the second copy when `<dir>` is the root):

   ```bash
   for d in "<dir>" "$(git -C "<dir>" rev-parse --show-toplevel 2>/dev/null)"; do grep -hA12 '^## Boards' "$d"/{CLAUDE.md,CLAUDE.local.md} 2>/dev/null; done | awk '!s[$0]++'
   ```

   Confirm a recorded port with `ls <port>`. If it is gone and the listing in 3 shows a port recorded nowhere, show both and ask whether it is that board; after a yes, offer to update the line. A native-USB name changes whenever the board moves to another Mac USB port.
2. A port the user named in this message.
3. The ports on USB (one `ls` piped to `grep`, because a multi-glob `ls` aborts in zsh on the first unmatched pattern):

   ```bash
   ls /dev/cu.* 2>/dev/null | grep -E 'usbserial|SLAB_USBtoUART|wchusbserial|usbmodem' || true
   ```

   Exactly one: use it, name it in your reply, and offer to record it under `## Boards` (in the file that has the section, else the project's committed `CLAUDE.md`; port names are not secrets). Zero: say no board is on USB, suggest the UART connector, and stop rather than flashing later when one appears. More than one: list them with the `boards:` labels of `check_toolchain.sh` and ask which. Never guess between ports and never loop over them: a flash to the wrong port overwrites another board.

Without a `## Boards` section, 2 and 3 still work; ask the user for whatever is still unknown (which board, which chip). Prefer the **UART** connector to native **USB**: a bridge keeps its name and survives a crashing firmware (`references/ports.md`).

### 2. Configure

- `idf.py -C "<dir>" set-target <chip>` once per fresh checkout. It clears `build/` and generates `sdkconfig` from `sdkconfig.defaults`.
- Instead of `menuconfig`, edit `sdkconfig.defaults` and regenerate. With `build/` present: `rm -f "<dir>/sdkconfig" && idf.py -C "<dir>" reconfigure`. Without `build/`, `reconfigure` silently falls back to target `esp32`, so run `set-target <chip>` instead. After either, confirm with `grep '^CONFIG_IDF_TARGET=' "<dir>/sdkconfig"`.
- Chip-specific keys (flash size, PSRAM) go in `sdkconfig.defaults.<chip>`. IDF applies it only when `sdkconfig.defaults` exists, so keep that file even if it holds only comments.
- A misspelled key is only a `warning: unknown kconfig symbol`: grep the configure output for it, then grep the generated `sdkconfig` for the keys that matter. Take keys from the project's docs, an Espressif example's `sdkconfig.defaults` or the IDF Kconfig files for that chip, not from memory.

### 3. Build

`idf.py -C "<dir>" build`. Read errors from the **first** `error:` line; the tail is CMake noise. The build is the authority on compile errors: an LSP diagnostic is a hint to confirm with a build, and on IDF sources it is noise unless the setup in `references/editor-clangd.md` is in place. Fix code in the project. `~/esp/esp-idf` is shared by every project and `managed_components/` is regenerated, so leave both alone: a failure inside a managed component gets reported with its first error and the component version, and a needed change goes into an override in the project's `components/` (`references/project-layout.md`). Fix warnings rather than hiding them with `-Wno-*` or `-fpermissive`. `idf.py -C "<dir>" size` when flash or RAM is in question.

### 4. Flash, an authorization boundary

Building is free. **Flashing is not.** Flash only when the user asked for it in this message ("flash it", "upload", "put it on the board"), and only to a port resolved in step 1. A request to build, fix or debug does not include flashing. This covers every route that writes the chip: the `idf.py` flash targets, esptool, and a monitor's `flash` command. Close any monitor on the port first.

A board wired to ESCs, motor drivers or actuators has two more rules: no flash and no `serial_tail.py --reset` until the user has confirmed motor power is disconnected, and a console command that spins a motor or moves an actuator is the user's to send, unless the project links the optional `motor-bench` skill and its checks pass.

Before flashing, check the build for eFuse burns on boot (Fixed decisions). The pattern holds every `sdkconfig` key that makes IDF v5.5 burn an eFuse at boot or on update: secure boot, signed apps, flash and NVS encryption, app anti-rollback, the ROM console and ROM log, the ECC and ECDSA modes. It must print nothing unless the user has confirmed the burn. It does not see project code that calls `esp_efuse_write*`; such a call needs the same confirmation.

```bash
grep -E '^CONFIG_(SECURE_(BOOT|SIGNED_APPS_NO_SECURE_BOOT|FLASH_ENC_ENABLED)|NVS_ENCRYPTION|BOOTLOADER_APP_ANTI_ROLLBACK|ESP32_DISABLE_BASIC_ROM_CONSOLE|BOOT_ROM_LOG_(ALWAYS_OFF|ON_GPIO_(LOW|HIGH))|ESP_CRYPTO_FORCE_ECC_CONSTANT_TIME_POINT_MUL|ESP_ECDSA_ENABLE_P192_CURVE)=y' "<dir>/sdkconfig"
```

```bash
idf.py -C "<dir>" -p "<port>" flash
```

**Erase.** `idf.py -C "<dir>" -p "<port>" erase-flash` wipes NVS, the partition table and every data partition (models, filesystems, calibration). Run it only after the user has answered yes to an explicit "erase the flash on <board>?" in this conversation; never chain it in "to be safe". In auto mode the permission classifier denies `erase-flash` and `esptool.py erase_flash` as irreversible even after that yes. Don't retry, rephrase or route around it (no `esptool` variant, no script wrapper): give the user the exact command to run with `!`, e.g. `! idf.py -C "<dir>" -p "<port>" erase-flash`, wait for its output, then continue with the flash.

If esptool cannot connect: report it, suggest holding **BOOT**, tapping **RESET**, releasing **BOOT** to force download mode, then retry once. More retries only hammer a board that needs a hand on it; report instead.

### 5. Watch the board

For the user at their own terminal: `idf.py -C "<dir>" -p "<port>" monitor`, exit with `Ctrl+]`. From a tool call, run the bounded reader instead (macOS has no `timeout`, which is why it exists); it needs the IDF venv's pyserial, so it takes the export prefix, and `python` there is the venv's:

```bash
. "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 && python "${CLAUDE_SKILL_DIR}/scripts/serial_tail.py" "<port>" -C "<dir>" --seconds 20 --reset
. "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 && python "${CLAUDE_SKILL_DIR}/scripts/serial_tail.py" "<port>" -C "<dir>" --seconds 30 --reset --until 'Found 8MB PSRAM'
```

`--reset` captures the boot from its first line, `--until <regex>` stops on a checkpoint, `--seconds` caps at 60. Exit 0 done or matched, 1 port error, 2 no match by the deadline, 3 usage, 4 output cap. On exit 1 with the port lost (a native USB port whose firmware sleeps, turns USB off or reset-loops), rerun once without `--reset`, then suggest the UART connector. Quote only the lines that decide it: the panic with its backtrace, or the checkpoint. Decoding and the full flags: `references/debugging.md`.

### 6. Report

One short paragraph: what was built, whether it was flashed and to which port, and the one boot line that proves the checkpoint. Full logs stay in the terminal.

## When delegating

From the main session, builds, `size` and other checks go to `verifier`, and fix-and-rebuild work to `fast-executor` or `implementer`. They have Bash but not this skill, so paste the block below into the prompt with `<dir>` and `<port>` filled in, and add a line for any environment fix the project's `CLAUDE.md` names (a `PATH` or `PYTHONPATH` override, for one). The reader's path in it is the installed link, which any shell resolves. Flashing, erasing, resets and choosing the port stay with you.

```text
ESP-IDF project at <dir>. Start every Bash call that runs idf.py or serial_tail.py with
  . "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 &&
and name the project in every idf.py call: idf.py -C "<dir>" build
Never write to or reset the board: no esptool or espefuse, no idf.py -p, and no idf.py target
containing flash, erase or efuse (flash, app-flash, bootloader-flash, partition-table-flash,
encrypted-flash, dfu-flash, erase-flash, erase-otadata, efuse-*).
Never run monitor, menuconfig, confserver, gdb* or openocd.
Never edit ~/esp/esp-idf or managed_components/; never pip install, never run install.sh.
Board logs only if this task asks for them, only through this command, never with --reset:
  python "$HOME/.claude/skills/esp-idf/scripts/serial_tail.py" "<port>" -C "<dir>" --seconds 20
On a failed build, quote the first line containing "error:", not the tail.
```

## Code rules

- Current driver headers only: `driver/i2s_std.h`, `driver/gptimer.h`, `driver/rmt_tx.h`, `driver/i2c_master.h`. Legacy `driver/{i2s,timer,rmt,adc,pcnt,mcpwm,dac,sigmadelta}.h` are deprecated in IDF 5 and removed in 6.0; legacy `driver/i2c.h` is end-of-life in 6.x (a compile-time message) and goes in 7.0. All are off limits. Legacy I2C compiles without a warning in IDF 5 and only complains at boot, so grep for the include.
- Credentials come from the project's secrets header, not from a literal in a source file, which would end up in a commit.
- ESP32-S3 GPIOs: strapping pins 0, 3, 45 and 46 set the boot mode, and IO35-37 are taken by the octal PSRAM on modules such as the N16R8. Check a new pin against the project's pin notes and the module datasheet before choosing it, and cite what you relied on.
