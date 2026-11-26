# Serial ports on macOS

Read from SKILL.md step 1 when a port is ambiguous, missing or busy. The resolution order and the confirmation steps stay in SKILL.md; this file only helps identify what is plugged in.

## Two connectors

The S3-DevKitC-1 (Micro-USB on the official board, USB-C on clones) and the C6-DevKitC-1 (USB-C) have two connectors: **UART**, through a USB-to-UART bridge chip, and **USB**, the chip's native USB-Serial-JTAG. The C3 devkits and the classic ESP32 DevKitC have one connector, which is the bridge.

Prefer UART. A bridge with a programmed serial number keeps its name wherever it is plugged in, and it survives a crashing firmware. The native port is named after the physical Mac USB port it sits in, re-enumerates on every reset (so `serial_tail.py --reset` loses the first boot lines), and vanishes if the firmware reconfigures USB or sleeps.

## Telling them apart

The device name does not reliably say which is which:

- CP210x and FTDI bridges: `/dev/cu.usbserial-<serial>` (CP210x as `/dev/cu.SLAB_USBtoUART` under Silicon Labs' driver).
- WCH CH340 and CH9102: `usbserial-*` or `wchusbserial*`.
- WCH CH343 is a CDC-class bridge and appears as `/dev/cu.usbmodem<serial>`, the same shape as the native port.

Identify by USB vendor ID: 0x303a native USB-Serial-JTAG, 0x10c4 CP210x, 0x1a86 WCH, 0x0403 FTDI. The `boards:` lines of `check_toolchain.sh` print each port with its vendor and product ID, product name and that label. By hand (no port names, decimal IDs: 12346, 4292, 6790, 1027):

```bash
ioreg -p IOUSB -l -w0 | grep -E '"(USB Product Name|idVendor|idProduct|USB Serial Number)"'
```

A `usbserial-0001` suffix is a generic serial shared by many cheap bridges, so two such boards cannot be told apart by name. Say so and ask the user to plug in one at a time.

## Nothing appears, or the port is busy

- macOS ships drivers for CP210x, FTDI and WCH CH340/CH9102, and a CH343 runs on the built-in CDC driver. No port after plugging the UART connector usually means a charge-only cable or a bad USB port: tell the user to try another. Installing a third-party driver (a DriverKit extension) changes the machine, so leave it to the user.
- `Resource busy` on open means another process holds the port: an old monitor, VS Code's serial view, Arduino IDE. Name the likely culprit and let the user close it rather than killing processes yourself.
