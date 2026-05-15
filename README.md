# TickForge

Tiny RPG-ish terminal timer for quick focus sessions.

![TickForge running timer](assets/screenshots/running-timer.png)

## Features

- Interactive pixel-art menu
- Presets for `6m`, `15m`, `1h`, `1h30m`, and `3h`
- Custom timers like `10s`, `5m`, or `1h30m`
- Desktop notification when the timer ends
- Stopwatch and Pomodoro modes
- Stored countdown timer history

## Install

```bash
cd ~/devz/tickforge
python -m pip install -e .
```

## Usage

```bash
tickforge
```

```bash
tickforge 10s
tickforge 5m --label Focus
tickforge stopwatch
tickforge pomodoro --work 25m --break-time 5m --cycles 4
tickforge history
```

## Notification

![TickForge notification](assets/screenshots/complete-notification.png)

## Controls

- `Ctrl+C` stops the timer.
- `--quiet` disables the bell.

## Timer History

Completed countdown timers are stored as JSON in your user data directory, for example
`~/.local/share/tickforge/timer_sessions.json` on Linux. If that location is
not writable, TickForge falls back to `.tickforge/timer_sessions.json` in the
project/current directory. Open the interactive menu and choose `History`,
or run:

```bash
tickforge history --limit 20
```
