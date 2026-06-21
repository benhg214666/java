#!/usr/bin/env python3
"""Generate scheduler-compatible periodic task sets for RTSPJT Level 1."""

from __future__ import annotations
from datetime import datetime

import argparse
import json
import math
import random
from dataclasses import dataclass
from fractions import Fraction
from datetime import datetime
from pathlib import Path
from typing import Any


HORIZON = 72
FRAME_SIZE = 4
MIN_TASKS = 6
MAX_TASKS = 10
MIN_DENSITY = Fraction(7, 10)
MAX_DENSITY = Fraction(9, 10)
PERIODS = (6, 8, 10, 12, 14, 15, 16, 18, 20, 24)
TIGHT_PERIODS = (8, 12, 16, 20, 24)


def find_project_root() -> Path:
    current_path = Path(__file__).resolve()
    for candidate in current_path.parents:
        if (candidate / "input").is_dir() and (candidate / "backend").is_dir():
            return candidate
    return current_path.parent.parent.parent


@dataclass(frozen=True)
class Task:
    r: int
    p: int
    e: int
    d: int
    w: int
    preempt: int

    def to_json(self) -> dict[str, int]:
        return {
            "r": self.r,
            "p": self.p,
            "e": self.e,
            "d": self.d,
            "w": self.w,
            "preempt": self.preempt,
        }


def frame_bound(period: int) -> int:
    return 2 * FRAME_SIZE - math.gcd(FRAME_SIZE, period)


def valid_releases(period: int, deadline: int) -> list[int]:
    releases = []
    for r in range(1, period + 1):
        last_release = r + ((HORIZON - r) // period) * period
        if last_release + deadline - 1 <= HORIZON:
            releases.append(r)
    return releases


def expanded_jobs_in_horizon(tasks: list[Task]) -> int:
    return sum(((HORIZON - task.r) // task.p) + 1 for task in tasks)


def workload_density(tasks: list[Task]) -> Fraction:
    return sum((Fraction(task.e, task.p) for task in tasks), Fraction(0, 1))


def validate_task_set(tasks: list[Task]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not MIN_TASKS <= len(tasks) <= MAX_TASKS:
        errors.append("task count must be between 6 and 10")
    if len({task.p for task in tasks}) < 3:
        errors.append("at least 3 different periods are required")
    if expanded_jobs_in_horizon(tasks) <= 30:
        errors.append("periodic jobs inside the 72-hour horizon must be > 30")
    if not MIN_DENSITY <= workload_density(tasks) <= MAX_DENSITY:
        errors.append("workload density must be between 0.7 and 0.9")
    if sum(1 for task in tasks if task.e == 2) < 2:
        errors.append("at least 2 tasks must have e = 2")
    if sum(1 for task in tasks if task.e >= 3) < 1:
        errors.append("at least 1 task must have e >= 3")
    if sum(1 for task in tasks if task.w >= 14) < 2:
        errors.append("at least 2 tasks must have w >= 14")
    if sum(1 for task in tasks if task.d == task.e) < math.ceil(len(tasks) * 0.2):
        errors.append("at least 20% of tasks must have d = e")
    if sum(1 for task in tasks if task.e != 1 and task.preempt == 0) < 2:
        errors.append("at least 2 tasks with e != 1 must be non-preemptive")

    for index, task in enumerate(tasks, start=1):
        prefix = f"p{index}"
        if not 1 <= task.r <= task.p:
            errors.append(f"{prefix}: release must satisfy 1 <= r <= p")
        if not 6 <= task.p <= 24:
            errors.append(f"{prefix}: period must be 6..24")
        if not 1 <= task.e <= 4:
            errors.append(f"{prefix}: execution must be 1..4")
        if not task.e <= task.d <= task.p:
            errors.append(f"{prefix}: deadline must satisfy e <= d <= p")
        if not 6 <= task.w <= 18:
            errors.append(f"{prefix}: energy demand must be 6..18")
        if task.preempt not in (0, 1):
            errors.append(f"{prefix}: preempt must be 0 or 1")
        if FRAME_SIZE < task.e:
            errors.append(f"{prefix}: frame size is smaller than execution time")
        if frame_bound(task.p) > task.d:
            errors.append(f"{prefix}: frame bound is larger than deadline")
        if task.r not in valid_releases(task.p, task.d):
            errors.append(f"{prefix}: last released job would exceed the 72-hour horizon")

    return not errors, errors


def build_candidate(rng: random.Random, task_count: int) -> list[Task] | None:
    tight_count = math.ceil(task_count * 0.2)
    tight_indices = set(rng.sample(range(task_count), tight_count))

    partial: list[dict[str, int]] = []
    for index in range(task_count):
        if index in tight_indices:
            period = rng.choice(TIGHT_PERIODS)
            execution = 4
            deadline = 4
        else:
            period = rng.choice(PERIODS)
            execution = rng.choice((1, 1, 2, 2, 3))
            lower_deadline = max(execution, frame_bound(period))
            if lower_deadline > period:
                return None
            deadline = rng.randint(lower_deadline, period)

        releases = valid_releases(period, deadline)
        if not releases:
            return None
        release_pool = releases[: max(1, math.ceil(len(releases) * 0.6))]
        partial.append(
            {
                "r": rng.choice(release_pool),
                "p": period,
                "e": execution,
                "d": deadline,
                "w": rng.randint(6, 18),
                "preempt": 1,
            }
        )

    e2_count = sum(1 for task in partial if task["e"] == 2)
    adjustable = [index for index, task in enumerate(partial) if index not in tight_indices]
    rng.shuffle(adjustable)
    for index in adjustable:
        if e2_count >= 2:
            break
        task = partial[index]
        task["e"] = 2
        task["d"] = max(task["d"], 2, frame_bound(task["p"]))
        if task["d"] > task["p"]:
            return None
        releases = valid_releases(task["p"], task["d"])
        if task["r"] not in releases:
            task["r"] = releases[0] if releases else 0
        e2_count += 1

    high_energy_indices = set(rng.sample(range(task_count), 2))
    for index in high_energy_indices:
        partial[index]["w"] = rng.randint(14, 18)

    non_preemptive_candidates = [index for index, task in enumerate(partial) if task["e"] != 1]
    if len(non_preemptive_candidates) < 2:
        return None
    for index in rng.sample(non_preemptive_candidates, 2):
        partial[index]["preempt"] = 0

    return [Task(**task) for task in partial]


def scheduler_compatible(tasks: list[Task], base_dir: Path) -> tuple[bool, list[str]]:
    try:
        import scheduler
    except Exception as exc:  # pragma: no cover - fallback for standalone use.
        return True, [f"scheduler compatibility check skipped: {exc}"]

    processor_path = base_dir / "input" / "processor_settings.json"
    price_path = base_dir / "input" / "price_72hr.json"
    if not processor_path.exists() or not price_path.exists():
        return True, ["scheduler compatibility check skipped: input JSON files not found"]

    scheduler_tasks = [
        scheduler.Task(
            task_id=f"p{index}",
            release_time=task.r,
            period=task.p,
            execution_time=task.e,
            deadline=task.d,
            energy=float(task.w),
            preemptive=task.preempt,
        )
        for index, task in enumerate(tasks, start=1)
    ]
    frame_errors = scheduler.validate_frame(scheduler_tasks)
    if frame_errors:
        return False, frame_errors

    jobs, skipped_jobs = scheduler.expand_periodic_jobs(scheduler_tasks)
    if skipped_jobs:
        return False, [f"{len(skipped_jobs)} jobs exceed the scheduling horizon"]
    if len(jobs) <= 30:
        return False, ["scheduler-expanded jobs inside horizon must be > 30"]

    settings = scheduler.load_json(processor_path)
    price_data = scheduler.load_json(price_path)
    success, scheduled_jobs, failed_jobs = scheduler.solve_job_times(
        jobs,
        scheduler.hour_scores(settings, price_data),
        scheduler.hourly_load_capacity(settings),
    )
    if not success or failed_jobs:
        return False, ["scheduler could not place every periodic job"]

    schedule_output = scheduler.build_schedule_result(
        scheduled_jobs,
        settings,
        price_data,
        skipped_jobs=[],
        failed_jobs=[],
    )
    verification_errors = scheduler.verify_schedule(
        scheduled_jobs,
        schedule_output["schedule_result"],
        settings,
    )
    return not verification_errors, verification_errors


def generate_task_set(
    base_dir: Path,
    task_count: int | None = None,
    seed: int | None = None,
    max_attempts: int = 20_000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rng = random.Random(seed)
    last_errors: list[str] = []

    for attempt in range(1, max_attempts + 1):
        count = task_count if task_count is not None else rng.randint(8, MAX_TASKS)
        tasks = build_candidate(rng, count)
        if tasks is None:
            continue

        ok, errors = validate_task_set(tasks)
        if not ok:
            last_errors = errors
            continue

        ok, errors = scheduler_compatible(tasks, base_dir)
        if not ok:
            last_errors = errors
            continue

        periodic = {
            f"p{index}": task.to_json()
            for index, task in enumerate(tasks, start=1)
        }
        metadata = {
            "attempts": attempt,
            "task_count": len(tasks),
            "periodic_jobs_in_horizon": expanded_jobs_in_horizon(tasks),
            "workload_density": round(float(workload_density(tasks)), 6),
            "frame_size": FRAME_SIZE,
            "seed": seed,
        }
        return {"periodic": periodic}, metadata

    raise RuntimeError(
        "failed to generate a scheduler-compatible task set; last errors: "
        + "; ".join(last_errors)
    )


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()
    parser = argparse.ArgumentParser(description="Generate output/task_set.json for RTSPJT Level 1.")
    parser.add_argument("--base-dir", type=Path, default=project_root)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=20_000)
    parser.add_argument("--metadata", action="store_true")
    return parser.parse_args()

def format_task_set_json(task_set: dict[str, Any]) -> str:
    lines = []
    lines.append("{")
    lines.append('    "periodic": {')

    periodic_items = list(task_set["periodic"].items())
    for index, (task_id, task_data) in enumerate(periodic_items):
        comma = "," if index < len(periodic_items) - 1 else ""
        task_json = json.dumps(task_data, ensure_ascii=False, separators=(", ", ": "))
        lines.append(f'        "{task_id}": {task_json}{comma}')

    extra_items = [(key, value) for key, value in task_set.items() if key != "periodic"]
    if extra_items:
        lines.append("    },")
        for index, (key, value) in enumerate(extra_items):
            comma = "," if index < len(extra_items) - 1 else ""
            value_json = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
            lines.append(f'    "{key}": {value_json}{comma}')
    else:
        lines.append("    }")

    lines.append("}")
    return "\n".join(lines)

def main() -> None:
    args = parse_args()
    if args.count is not None and not MIN_TASKS <= args.count <= MAX_TASKS:
        raise ValueError("--count must be between 6 and 10")

    base_dir = args.base_dir.resolve()
    output_path = args.output.resolve() if args.output else base_dir / "output" / "task_set.json"

    task_set, metadata = generate_task_set(
    base_dir=base_dir,
        task_count=args.count,
        seed=args.seed,
        max_attempts=args.max_attempts,
    )
    if args.metadata:
        task_set["_meta"] = metadata

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_task_set_json(task_set), encoding="utf-8")
    written_stat = output_path.stat()

    print("=== Task Generator ===")
    print(f"tasks: {metadata['task_count']}")
    print(f"periodic jobs in horizon: {metadata['periodic_jobs_in_horizon']}")
    print(f"workload density: {metadata['workload_density']}")
    print(f"frame size: {metadata['frame_size']}")
    print(f"attempts: {metadata['attempts']}")
    print(f"overwrote: {output_path}")
    print(f"file size: {written_stat.st_size} bytes")
    print(f"modified: {datetime.fromtimestamp(written_stat.st_mtime).isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
