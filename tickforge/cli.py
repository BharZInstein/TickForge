from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SPAN_PATTERN = re.compile(r"(?P<value>\d+)(?P<unit>[hms]?)", re.IGNORECASE)
PIXEL_HOURGLASS = [
    "   ▄████▄   ",
    "  █▀    ▀█  ",
    "   █▄  ▄█   ",
    "    ▀██▀    ",
    "    ▄██▄    ",
    "   █▀  ▀█   ",
    "  █▄    ▄█  ",
    "   ▀████▀   ",
]
RESET = "\033[0m"
COLORS = {
    "amber": "\033[38;5;214m",
    "cyan": "\033[38;5;81m",
    "green": "\033[38;5;120m",
    "magenta": "\033[38;5;207m",
    "muted": "\033[38;5;244m",
    "red": "\033[38;5;203m",
    "white": "\033[38;5;255m",
}


@dataclass(frozen=True)
class TimerConfig:
    seconds: int
    label: str
    quiet: bool
    record: bool = True


@dataclass(frozen=True)
class TimerSession:
    completed_at: str
    label: str
    seconds: int


def parse_span(value: str) -> int:
    raw_value = value.strip().lower()
    if not raw_value:
        raise argparse.ArgumentTypeError("duration cannot be empty")

    total = 0
    position = 0
    for match in SPAN_PATTERN.finditer(raw_value):
        if match.start() != position:
            raise argparse.ArgumentTypeError(f"invalid duration: {value}")
        amount = int(match.group("value"))
        unit = match.group("unit") or "s"
        multiplier = {"h": 3600, "m": 60, "s": 1}[unit]
        total += amount * multiplier
        position = match.end()

    if position != len(raw_value) or total <= 0:
        raise argparse.ArgumentTypeError(f"invalid duration: {value}")
    return total


def format_time(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def candidate_data_dirs() -> list[Path]:
    candidates = []
    if sys.platform == "win32":
        root = os.environ.get("APPDATA")
        candidates.append(Path(root) / "TickForge" if root else Path.home() / "AppData" / "Roaming" / "TickForge")
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "TickForge")
    else:
        candidates.append(Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "tickforge")

    candidates.append(Path(__file__).resolve().parents[1] / ".tickforge")
    candidates.append(Path.cwd() / ".tickforge")
    return list(dict.fromkeys(candidates))


def can_write_data_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_path = path / ".write-test"
        test_path.write_text("", encoding="utf-8")
        test_path.unlink()
    except OSError:
        return False
    return True


def data_dir() -> Path:
    candidates = candidate_data_dirs()
    for candidate in candidates:
        if (candidate / "timer_sessions.json").exists():
            return candidate
    for candidate in candidates:
        if can_write_data_dir(candidate):
            return candidate
    return candidates[0]


def history_path() -> Path:
    return data_dir() / "timer_sessions.json"


def read_timer_sessions() -> list[TimerSession]:
    path = history_path()
    if not path.exists():
        return []

    try:
        raw_sessions = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    sessions = []
    for raw_session in raw_sessions if isinstance(raw_sessions, list) else []:
        if not isinstance(raw_session, dict):
            continue
        try:
            sessions.append(
                TimerSession(
                    completed_at=str(raw_session["completed_at"]),
                    label=str(raw_session["label"]),
                    seconds=int(raw_session["seconds"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sessions


def write_timer_sessions(sessions: list[TimerSession]) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "completed_at": session.completed_at,
            "label": session.label,
            "seconds": session.seconds,
        }
        for session in sessions
    ]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def store_timer_session(label: str, seconds: int) -> None:
    completed_at = datetime.now().astimezone()
    session = TimerSession(
        completed_at=f"{completed_at.strftime('%B')} {completed_at.day}, {completed_at.year}",
        label=label,
        seconds=seconds,
    )
    sessions = read_timer_sessions()
    sessions.append(session)
    write_timer_sessions(sessions)


def format_completed_at(value: str) -> str:
    try:
        completed_at = datetime.fromisoformat(value)
    except ValueError:
        return value
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    return completed_at.astimezone().strftime("%Y-%m-%d %H:%M")


def print_timer_history(limit: int | None = None) -> None:
    sessions = read_timer_sessions()
    if not sessions:
        sys.stdout.write("No timer sessions stored yet.\n")
        return

    visible_sessions = sessions[-limit:] if limit else sessions
    total_time = sum(session.seconds for session in sessions)
    total_sessions = len(sessions)
    lines = [
        f"Stored sessions: {paint(str(total_sessions), 'green')}",
        f"Total time: {paint(format_duration(total_time), 'green')}",
        f"History file: {paint(str(history_path()), 'muted')}",
    ]
    sys.stdout.write(boxed(lines, "Timer Ledger"))
    sys.stdout.write("\n\n")

    rows = []
    offset = total_sessions - len(visible_sessions)
    for index, session in enumerate(visible_sessions, start=offset + 1):
        rows.append(
            f"{index:>3}. {format_completed_at(session.completed_at)}  "
            f"{session.label}  {format_duration(session.seconds)}"
        )
    sys.stdout.write(boxed(rows, "Recent Sessions"))
    sys.stdout.write("\n")


def supports_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, color: str) -> str:
    if not supports_color():
        return text
    return f"{COLORS[color]}{text}{RESET}"


def visible_width(text: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", text))


def boxed(lines: list[str], title: str = "") -> str:
    width = max([visible_width(line) for line in lines] + [len(title)])
    top = f"╔═ {title} {'═' * max(0, width - len(title) - 1)}╗" if title else f"╔{'═' * (width + 2)}╗"
    body = [f"║ {line}{' ' * (width - visible_width(line))} ║" for line in lines]
    bottom = f"╚{'═' * (width + 2)}╝"
    return "\n".join([top, *body, bottom])


def progress_bar(remaining: int, total: int, width: int = 24) -> str:
    elapsed = max(0, total - remaining)
    filled = min(width, round((elapsed / total) * width)) if total else width
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def render(status: str, seconds: int, total: int | None = None) -> None:
    if total is None or not sys.stdout.isatty():
        sys.stdout.write(f"\r{status} {format_time(seconds)}")
        sys.stdout.flush()
        return

    line = (
        f"\r{paint('⚔', 'amber')} {paint(status, 'cyan')} "
        f"{paint(format_time(seconds), 'white')} {paint(progress_bar(seconds, total), 'green')}"
    )
    sys.stdout.write(f"{line}\033[K")
    sys.stdout.flush()


def notify(title: str, message: str) -> None:
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False, stderr=subprocess.DEVNULL)
        return
    if sys.platform == "darwin" and shutil.which("osascript"):
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", script], check=False, stderr=subprocess.DEVNULL)
        return
    if sys.platform == "win32" and shutil.which("powershell"):
        safe_title = title.replace("'", "''")
        safe_message = message.replace("'", "''")
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
            "$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
            "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);"
            f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{safe_title}')) > $null;"
            f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{safe_message}')) > $null;"
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('TickForge').Show($toast);"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False, stderr=subprocess.DEVNULL)


def finish(label: str, quiet: bool) -> None:
    notify("TickForge", f"{label} is done.")
    sound = "" if quiet else "\a"
    message = f"✦ {label} complete. Quest reward claimed. ✦"
    sys.stdout.write(f"\r{paint(message, 'green')}{' ' * 16}{sound}\n")
    sys.stdout.flush()


def run_countdown(config: TimerConfig) -> int:
    end_at = time.monotonic() + config.seconds
    try:
        while True:
            remaining = round(end_at - time.monotonic())
            if remaining <= 0:
                break
            render(config.label, remaining, config.seconds)
            time.sleep(min(1, remaining))
    except KeyboardInterrupt:
        sys.stdout.write(f"\n{paint('Quest abandoned.', 'red')}\n")
        return 130

    finish(config.label, config.quiet)
    if config.record:
        try:
            store_timer_session(config.label, config.seconds)
        except OSError as error:
            sys.stdout.write(f"{paint(f'Could not store timer session: {error}', 'red')}\n")
    return 0


def run_stopwatch(label: str) -> int:
    started_at = time.monotonic()
    try:
        while True:
            elapsed = round(time.monotonic() - started_at)
            render(label, elapsed)
            time.sleep(1)
    except KeyboardInterrupt:
        elapsed = round(time.monotonic() - started_at)
        sys.stdout.write(f"\n{paint('Stopped at', 'amber')} {format_time(elapsed)}.\n")
        return 0


def run_pomodoro(work: int, break_time: int, cycles: int, quiet: bool) -> int:
    for cycle in range(1, cycles + 1):
        result = run_countdown(TimerConfig(work, f"Focus {cycle}/{cycles}", quiet=True, record=False))
        if result:
            return result
        if cycle == cycles:
            break
        result = run_countdown(TimerConfig(break_time, f"Break {cycle}/{cycles}", quiet=True, record=False))
        if result:
            return result

    finish("Pomodoro", quiet)
    return 0


def clear_screen() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def prompt(text: str) -> str:
    return input(paint(text, "amber"))


def prompt_choice() -> str:
    presets = [
        ("1", "6 minutes", "6m"),
        ("2", "15 minutes", "15m"),
        ("3", "1 hour", "1h"),
        ("4", "1.5 hours", "1h30m"),
        ("5", "3 hours", "3h"),
        ("6", "Custom", ""),
        ("7", "History", "history"),
    ]

    art = [paint(line, "magenta") for line in PIXEL_HOURGLASS]
    menu = [f"{paint(key + ')', 'amber')} {label}" for key, label, _duration in presets]

    clear_screen()
    sys.stdout.write(boxed(art, "TickForge Timer Guild"))
    sys.stdout.write("\n\n")
    sys.stdout.write(boxed(menu, "Choose Your Quest"))
    sys.stdout.write("\n\n")
    sys.stdout.write(paint("Tip: custom accepts 10s, 5m, 1h30m.\n\n", "muted"))
    sys.stdout.write(paint("Choose a timer: ", "amber"))
    sys.stdout.flush()

    selected = input().strip()
    for key, _label, duration in presets:
        if selected == key:
            if duration == "history":
                return duration
            return prompt("Enter duration (e.g. 90s, 5m, 1h30m): ").strip() if not duration else duration
    raise ValueError("unknown menu choice")


def run_menu() -> int:
    while True:
        try:
            duration = prompt_choice()
            if duration == "history":
                print_timer_history(limit=12)
                sys.stdout.write("\nPress Enter to return to the menu, or Ctrl+C to quit.")
                sys.stdout.flush()
                try:
                    input()
                except KeyboardInterrupt:
                    sys.stdout.write("\n")
                    return 130
                except EOFError:
                    sys.stdout.write("\n")
                    return 0
                continue
            seconds = parse_span(duration)
            label = prompt("Quest name [Timer]: ").strip() or "Timer"
            quiet_answer = prompt("Ring bell when done? [Y/n]: ").strip().lower()
            quiet = quiet_answer in {"n", "no"}
            sys.stdout.write("\n")
            return run_countdown(TimerConfig(seconds, label, quiet))
        except (argparse.ArgumentTypeError, ValueError) as error:
            sys.stdout.write(f"\n{paint(str(error), 'red')}\nPress Enter to try again, or Ctrl+C to quit.")
            sys.stdout.flush()
            try:
                input()
            except KeyboardInterrupt:
                sys.stdout.write("\n")
                return 130
            except EOFError:
                sys.stdout.write("\n")
                return 0
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            return 130
        except EOFError:
            sys.stdout.write("\n")
            return 0


def build_countdown_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tickforge",
        description="Run a countdown timer.",
    )
    parser.add_argument("duration", type=parse_span, help="countdown duration, e.g. 90s, 5m, 1h30m")
    parser.add_argument("--label", default="Timer", help="status label for countdown mode")
    parser.add_argument("--quiet", action="store_true", help="do not ring the terminal bell")
    return parser


def build_stopwatch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tickforge stopwatch",
        description="Run a stopwatch until Ctrl+C.",
    )
    parser.add_argument("--label", default="Stopwatch", help="status label")
    return parser


def build_pomodoro_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tickforge pomodoro",
        description="Run Pomodoro work/break cycles.",
    )
    parser.add_argument("--work", type=parse_span, default=parse_span("25m"), help="work duration")
    parser.add_argument("--break-time", type=parse_span, default=parse_span("5m"), help="break duration")
    parser.add_argument("--cycles", type=int, default=4, help="number of work cycles")
    parser.add_argument("--quiet", action="store_true", help="do not ring the terminal bell")
    return parser


def build_timer_history_parser(prog: str = "tickforge history") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Show stored countdown timer sessions.",
    )
    parser.add_argument("--limit", type=int, default=12, help="number of recent sessions to show; use 0 for all")
    return parser


def print_overview() -> None:
    sys.stdout.write(
        "usage: tickforge\n"
        "       tickforge <duration> [--label LABEL] [--quiet]\n"
        "       tickforge stopwatch [--label LABEL]\n"
        "       tickforge pomodoro [--work DURATION] [--break-time DURATION] [--cycles N] [--quiet]\n"
        "       tickforge history [--limit N]\n\n"
        "Terminal countdown, stopwatch, and Pomodoro timer.\n\n"
        "examples:\n"
        "  tickforge\n"
        "  tickforge 5m\n"
        "  tickforge 1h30m --label DeepWork\n"
        "  tickforge stopwatch\n"
        "  tickforge pomodoro --cycles 4\n"
        "  tickforge history\n"
    )


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv

    if not arguments:
        return run_menu()
    if arguments[0] in {"-h", "--help"}:
        print_overview()
        return 0
    if arguments[0] == "stopwatch":
        args = build_stopwatch_parser().parse_args(arguments[1:])
        return run_stopwatch(args.label)
    if arguments[0] == "pomodoro":
        parser = build_pomodoro_parser()
        args = parser.parse_args(arguments[1:])
        if args.cycles <= 0:
            parser.error("--cycles must be greater than 0")
        return run_pomodoro(args.work, args.break_time, args.cycles, args.quiet)
    if arguments[0] in {"history", "timer-history", "pomodoro-history"}:
        parser = build_timer_history_parser(f"tickforge {arguments[0]}")
        args = parser.parse_args(arguments[1:])
        if args.limit < 0:
            parser.error("--limit must be 0 or greater")
        print_timer_history(limit=args.limit or None)
        return 0

    args = build_countdown_parser().parse_args(arguments)
    return run_countdown(TimerConfig(args.duration, args.label, args.quiet))


if __name__ == "__main__":
    raise SystemExit(main())
