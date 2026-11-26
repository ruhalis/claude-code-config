# Reading the board: serial_tail.py, panics, scripted monitor

Read from SKILL.md step 5 for the reader's full behaviour, to decode a panic, or before using esp-idf-monitor's scripted mode. Every command here runs in the export shell (`. "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 && ...`).

## serial_tail.py in detail

- Baud: `-C "<dir>"` reads `CONFIG_ESPTOOLPY_MONITOR_BAUD` from the project's `sdkconfig` (115200 without one); the first output line says which baud it used; `--baud <n>` overrides.
- `--reset` pulses the board so the boot log is captured from its first line. On a native USB-Serial-JTAG port (vendor 0x303a) the reset makes the port re-enumerate: the reader waits up to 5 s, prints `[serial_tail] port re-enumerated` and reads on, but the lines printed before the reopen are lost. For the whole boot log use the UART connector.
- `--until <regex>` stops on the first matching line: boot checkpoints such as the PSRAM size, an IP address, a "ready" line.
- Limits: `--seconds` is capped at 60; `--max-lines` (default 400), a 64 KB output cap and a 512-byte line cap stop a chatty firmware from flooding the call.
- Exit codes:
  - 0: done, or `--until` matched.
  - 1: port error. It could not open or reset the port, or the port was lost and not back within 5 s or before `--seconds` ran out.
  - 2: deadline passed without an `--until` match.
  - 3: usage or environment error (bad arguments, regex or `-C` directory, no pyserial).
  - 4: `--max-lines` or the output cap reached before an `--until` match.

## Decoding a panic

Backtraces come out raw. Decode them with the chip's toolchain from the export shell:

- **Xtensa (ESP32, S2, S3):** `xtensa-esp-elf-addr2line -pfiaC -e "<dir>/build/<project>.elf" <addr> ...` on the `Backtrace:` addresses.
- **RISC-V (C-, H-, P-series):** the panic prints registers and a stack dump, no backtrace. Save the panic text to `<dir>/build/panic.txt` and check `command -v riscv32-esp-elf-gdb`.
  - If it is there: `riscv32-esp-elf-gdb --batch -n "<dir>/build/<project>.elf" -ex 'target remote | python -m esp_idf_panic_decoder "<dir>/build/panic.txt"' -ex bt`.
  - If not (it comes only with a C-, H- or P-series chip in `install.sh`; see the `gdb:` line of `check_toolchain.sh`): say so, decode `MEPC` and `RA` from the register dump with `riscv32-esp-elf-addr2line -pfiaC -e "<dir>/build/<project>.elf" <MEPC> <RA>`, and tell the user that `./install.sh <chip>` adds the gdb. That is a toolchain change, so only when they ask.

## Scripted esp-idf-monitor (secondary to serial_tail.py)

esp-idf-monitor 1.10 and newer takes scripted commands on a piped stdin (`reset`, `expect --timeout <s> <regex>`, `exit`) and decodes backtraces on the way (on RISC-V only with `riscv32-esp-elf-gdb`).

- Use it only after `python -m pip show esp-idf-monitor` in the export shell reports 1.10 or newer. 1.9 and older exit at once with a TTY error.
- End the piped script in `exit` or an `expect --timeout`: on empty stdin 1.10 watches until killed.
- Its commands include `flash` and `app-flash`. Never pipe those: they write the chip and cross the flash boundary of SKILL.md step 4.
- The monitor still opens and resets the port, so it is a main-session action like `serial_tail.py --reset`.
- IDF 5.5's constraints allow 1.10. The user gets it by re-running `cd ~/esp/esp-idf && ./install.sh <chips>`, a machine change, only when they ask. Don't `pip install` it into the venv: `install.sh` owns that environment.
