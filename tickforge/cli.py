from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass


SPAN_PATTERN = re.compile(r"(?P<value>\d+)(?P<unit>[hms]?)", re.IGNORECASE)


@dataclass(frozen=True)
class TimerConfig:
    seconds: int
    label: str
    quiet: bool


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


def render(status: str, seconds: int) -> None:
    sys.stdout.write(f"\r{status} {format_time(seconds)}")
    sys.stdout.flush()


def finish(label: str, quiet: bool) -> None:
    sound = "" if quiet else "\a"
    sys.stdout.write(f"\r{label} done.{' ' * 16}{sound}\n")
    sys.stdout.flush()


def run_countdown(config: TimerConfig) -> int:
    end_at = time.monotonic() + config.seconds
    try:
        while True:
            remaining = round(end_at - time.monotonic())
            if remaining <= 0:
                break
            render(config.label, remaining)
            time.sleep(min(1, remaining))
    except KeyboardInterrupt:
        sys.stdout.write("\nStopped.\n")
        return 130

    finish(config.label, config.quiet)
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
        sys.stdout.write(f"\nStopped at {format_time(elapsed)}.\n")
        return 0


def run_pomodoro(work: int, break_time: int, cycles: int, quiet: bool) -> int:
    for cycle in range(1, cycles + 1):
        result = run_countdown(TimerConfig(work, f"Focus {cycle}/{cycles}", quiet=True))
        if result:
            return result
        if cycle == cycles:
            break
        result = run_countdown(TimerConfig(break_time, f"Break {cycle}/{cycles}", quiet=True))
        if result:
            return result

    finish("Pomodoro", quiet)
    return 0


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def prompt_choice() -> str:
    presets = [
        ("1", "10 seconds", "10s"),
        ("2", "1 minute", "1m"),
        ("3", "5 minutes", "5m"),
        ("4", "10 minutes", "10m"),
        ("5", "25 minutes", "25m"),
        ("6", "Custom", ""),
    ]

    clear_screen()
    sys.stdout.write("TickForge\n")
    sys.stdout.write("---------\n")
    for key, label, _duration in presets:
        sys.stdout.write(f"{key}) {label}\n")
    sys.stdout.write("\nChoose a timer: ")
    sys.stdout.flush()

    selected = input().strip()
    for key, _label, duration in presets:
        if selected == key:
            return input("Enter duration (e.g. 90s, 5m, 1h30m): ").strip() if not duration else duration
    raise ValueError("unknown menu choice")


def run_menu() -> int:
    while True:
        try:
            duration = prompt_choice()
            seconds = parse_span(duration)
            label = input("Label [Timer]: ").strip() or "Timer"
            quiet_answer = input("Ring bell when done? [Y/n]: ").strip().lower()
            quiet = quiet_answer in {"n", "no"}
            sys.stdout.write("\n")
            return run_countdown(TimerConfig(seconds, label, quiet))
        except (argparse.ArgumentTypeError, ValueError) as error:
            sys.stdout.write(f"\n{error}\nPress Enter to try again, or Ctrl+C to quit.")
            sys.stdout.flush()
            try:
                input()
            except KeyboardInterrupt:
                sys.stdout.write("\n")
                return 130
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            return 130


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


def print_overview() -> None:
    sys.stdout.write(
        "usage: tickforge\n"
        "       tickforge <duration> [--label LABEL] [--quiet]\n"
       "       tickforge stopwatch [--label LABEL]\n"
       "       tickforge pomodoro [--work DURATION] [--break-time DURATION] [--cycles N] [--quiet]\n\n"
        "Terminal countdown, stopwatch, and Pomodoro timer.\n\n"
        "examples:\n"
        "  tickforge\n"
        "  tickforge 5m\n"
        "  tickforge 1h30m --label DeepWork\n"
        "  tickforge stopwatch\n"
        "  tickforge pomodoro --cycles 4\n"
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

    args = build_countdown_parser().parse_args(arguments)
    return run_countdown(TimerConfig(args.duration, args.label, args.quiet))


if __name__ == "__main__":
    raise SystemExit(main())
