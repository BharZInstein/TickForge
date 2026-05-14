# TickForge

Tiny RPG-ish terminal timer.

## Install

```bash
cd ~/devz/tickforge
python -m pip install -e .
```

## Use

```bash
tickforge
```

Pick a preset or enter a custom time like `10s`, `5m`, or `1h30m`.

```bash
tickforge 10s
tickforge 5m --label Focus
tickforge stopwatch
tickforge pomodoro --work 25m --break-time 5m --cycles 4
```

## Controls

- `Ctrl+C` stops the timer.
- `--quiet` disables the bell.
- Desktop notifications are sent when supported.
