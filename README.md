# TickForge

TickForge is a small installable terminal timer with an interactive menu, quick countdowns, a stopwatch, and Pomodoro sessions.

## Install

```bash
cd ~/devz/tickforge
python -m pip install -e .
```

## Use the menu

Run TickForge without arguments to open the timer menu:

```bash
tickforge
```

Pick a preset or choose a custom duration like `10s`, `5m`, or `1h30m`.

## Quick commands

```bash
tickforge 10s
tickforge 5m --label Focus
tickforge stopwatch
tickforge pomodoro --work 25m --break-time 5m --cycles 4
```

## Controls

- Press `Ctrl+C` once to stop the active timer cleanly.
- Pass `--quiet` to skip the terminal bell when a timer finishes.
- TickForge sends a desktop notification when a timer finishes if your system supports terminal-triggered notifications.
