# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Stand is a Python console application for controlling an IR lamp experiment via Arduino. It plays sine wave tones at incrementing frequencies while triggering an IR lamp, logging timestamps for later correlation with camera photos.

## Running the Application

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the console
python stand.py
```

## Architecture

Single-file application (`stand.py`) with two main classes:

### CommandStateMachine
State machine using `transitions` library with states: `idle → ready → running ↔ paused → stopped`. Controls whether the frequency loop is active.

### StandConsole
Interactive console (extends `cmd.Cmd`) that manages:
- **Serial communication**: Auto-connects to Arduino on startup for IR lamp control
- **Audio generation**: Plays sine waves via `sounddevice` with streaming callbacks
- **Two background threads**:
  - `_loop_worker`: Plays tones at incrementing frequencies, signals IR thread
  - `_ir_worker`: Waits for signal, delays, sends IR command, logs to `stand.log`
- **Camera integration**: Fetches photos and renames based on log timestamps

### Thread Synchronization
- `loop_stop_event`: Signals both threads to stop
- `ir_trigger_event`: Coordinates IR command timing with sound loop iterations
- `output_lock`: Prevents console output corruption from concurrent prints

## Configuration

All settings in `stand.conf` (INI format). Key sections:
- `[serial]`: port, baudrate
- `[commands]`: ir_engage, test (escape sequences like `!r\n`)
- `[loop]`: current_frequency (persisted), step, duration, ir_delay, loop_sleep

## External Dependencies

- Arduino connected via serial (sends IR commands)
- Camera mounted via gvfs/MTP (for `fetch` command)
- gphoto2 (for `sync` command to set camera time)
