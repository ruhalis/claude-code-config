---
name: motor-bench
description: Safety rules for any command that spins a motor or moves an actuator - ESC bench tests, throttle sweeps, thrust stands, arm/disarm, flight sequences, missions, hover, CAN or serial actuator tests (torque, kP/kD, calibration). Use whenever the user mentions a motor, ESC, prop, throttle, spin test, actuator, servo, BLDC, e-stop or kill switch, or asks to run anything that makes hardware move, and with esp-idf when flashing or resetting a board wired to ESCs or drivers. Not for simulation (isaac).
compatibility: Main session only. Sending needs the project's own sender tool and the board or bus on this Mac. No bundled scripts.
---

# Motor bench

A wrong byte can spin a prop into a hand or drive a joint into its stop. A moving command is anything that can put current through a motor or change an actuator's target: a console key or line, a script setting mode, gains, torque or position, and a flash or reset of a board wired to powered ESCs or drivers. A dry-run variant counts while motor power is connected, since one lost argument makes it live. The stop is not moving: on the bench, send it whenever needed without asking.

## Project facts

Use the project's `## Motors` section in CLAUDE.md if there is one; most projects have none. Before the first moving command, get from it, the source (file:line) or the user: what moves and its power (supply and current limit, or battery); the interface (port and baud, or CAN bus) and the tool allowed to send; how to recognise the program on it (banner or harmless probe), since two boards can give one key opposite meanings; the stop command and the line confirming it; the firmware's limits; the user-only commands; the physical kill. Ask for what you can't find; never guess a stop command. Don't write these into the project; offer the user a `## Motors` draft instead.

## Hard limits

These hold even when the user asks otherwise.

1. Flight, arming for flight, hover, missions, any whole-vehicle or whole-robot motion, ESC throttle-range calibration (full throttle), and anything sent over radio or network belong to the user: prepare and explain the exact command; never send it. While armed or airborne every command is theirs, the stop included: tell them to land or kill it. A dry run of these goes out only once the user confirms, in this or the previous message, that motor power is unplugged.
2. Never flash or reset a board wired to ESCs or drivers until the user confirms motor power is disconnected; then say what the new image does to the motors at boot.
3. Never change a cap, slew limit, dead-man or watchdog timeout, arming check, failsafe, motor-cut timer, torque or current limit, or default gain to make a test pass. Change one only when asked, as old -> new with file:line, in its own change.
4. Never stop with SIGKILL or by closing the port: that skips the handler and leaves the last target live until a watchdog fires, if any. Use the stop command, or SIGINT to a script whose handler switches to damping.
5. Never send a moving command from a loop, retry, background job or schedule, chained behind a build, flash or other test, or as a side effect of another task; only through the project's sender tool, never an improvised serial or CAN writer.
6. No physical kill in the user's reach: send nothing that moves; hand over the commands.

## Before each test

- The user asked for this test, in their current message or the one before your pre-condition question.
- The user answered the pre-conditions, per setup and after any change (props, wiring, power, program, a level above the last confirmed): props off or guarded; actuator clamped or robot on a stand, joints free; area clear; power source and limit; kill in reach, stop tried at idle. Unanswered is not confirmed.
- Banner or probe confirms the program (reset only with motor power off); else hand the user the command.
- You stated what moves, at what level (µs, %, A, Nm, kP/kD), for how long, and what stops it.

## Running and stopping

Every test has a level cap and a duration; prefer the firmware's caps and timed tests to holding a level from the host. Lowest level first, one motor at a time, all together only after each passed alone; step up only after reporting the numbers and the user asking. Raising a runtime cap needs the value in the user's message. A command that holds a level goes out only with its stop in the same bounded call, else the user runs it; only the stop may follow a moving command in one call.

Send the stop on every exit path: done, error, timeout, odd output, tool failure, interruption, doubt the command arrived. Quote the line confirming it; unconfirmed, open your reply by telling the user to use the physical kill now. After a failure, stop, report, wait. Read with bounded tools only (`serial_tail.py --seconds/--until`); if the user's monitor holds the port, leave it.

Weaker rigs tighten this. Unknown or mixed ESCs: assume throttle maps differ, compare motors at one level. No current limit: lowest level, shortest run, one motor, no cap raise. No telemetry: the user says "stopped" before anything else goes out; never step up by sound.

## Reporting and code

Give each number against its limit (current, RPM, temperature, torque, position error, voltage sag, faults, direction); mark the rest `not measured`, and sound, smell or heat as the user's. One record line per test, in the project's log if it names one.

Code that commands motors may be written freely; running it follows these rules. It stops or switches to damping on every exit path, has a hard duration, and stays within the project's configured limits.
