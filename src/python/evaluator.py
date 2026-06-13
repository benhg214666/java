#!/usr/bin/env python3
"""Evaluate RTSPJT schedule_result.json and write evaluation_results.json."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


HORIZON = 72
EPS = 1e-7
APERIODIC_MISS_PENALTY = 10_000


def find_project_root() -> Path:
    current_path = Path(__file__).resolve()
    for candidate in current_path.parents:
        if (candidate / "input").is_dir() and (candidate / "src").is_dir():
            return candidate
    return current_path.parent.parent.parent


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def acceptance_sets(acceptance_log: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    sporadic_ids = {item["job_id"] for item in acceptance_log.get("sporadic", [])}
    accepted_sporadic_ids = {
        item["job_id"]
        for item in acceptance_log.get("sporadic", [])
        if item.get("accepted", False)
    }
    aperiodic_ids = {item["job_id"] for item in acceptance_log.get("aperiodic", [])}
    return sporadic_ids, accepted_sporadic_ids, aperiodic_ids


def infer_job_type(job_id: str, sporadic_ids: set[str], aperiodic_ids: set[str]) -> str:
    if job_id in sporadic_ids:
        return "sporadic"
    if job_id in aperiodic_ids:
        return "aperiodic"
    if job_id.startswith("s"):
        return "sporadic"
    if job_id.startswith("a"):
        return "aperiodic"
    return "periodic"


def collect_jobs(
    schedule_data: dict[str, Any],
    acceptance_log: dict[str, Any],
) -> list[dict[str, Any]]:
    sporadic_ids, _, aperiodic_ids = acceptance_sets(acceptance_log)
    jobs = []
    for item in schedule_data.get("job_schedule", []):
        job = dict(item)
        job["job_type"] = infer_job_type(job["job_id"], sporadic_ids, aperiodic_ids)
        if job.get("completion_time") is None and job.get("scheduled_times"):
            job["completion_time"] = max(job["scheduled_times"])
        jobs.append(job)
    return jobs


def calculate_deadline_metrics(
    jobs: list[dict[str, Any]],
    acceptance_log: dict[str, Any],
) -> dict[str, Any]:
    hard_jobs = [job for job in jobs if job["job_type"] in ("periodic", "sporadic")]
    hard_misses = [
        job for job in hard_jobs
        if job.get("completion_time") is None
        or int(job["completion_time"]) > int(job["absolute_deadline"])
    ]

    response_times = [
        int(job["completion_time"]) - int(job["release_time"])
        for job in jobs
        if job.get("completion_time") is not None
    ]
    tardiness_values = [
        max(0, int(job["completion_time"]) - int(job["absolute_deadline"]))
        for job in jobs
        if job.get("completion_time") is not None
    ]

    aperiodic_log = acceptance_log.get("aperiodic", [])
    if aperiodic_log:
        soft_misses = [item for item in aperiodic_log if item.get("miss", False)]
        soft_deadline_miss_rate = len(soft_misses) / len(aperiodic_log)
        aperiodic_tardiness = [float(item.get("tardiness", 0.0)) for item in aperiodic_log]
    else:
        soft_misses = []
        soft_deadline_miss_rate = 0.0
        aperiodic_tardiness = []

    jitter_values = []
    periodic_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        if job["job_type"] == "periodic" and job.get("completion_time") is not None:
            periodic_by_task[str(job["task_id"])].append(job)
    for task_jobs in periodic_by_task.values():
        task_jobs.sort(key=lambda job: int(job["release_time"]))
        completions = [int(job["completion_time"]) for job in task_jobs]
        if len(completions) >= 2:
            intervals = [b - a for a, b in zip(completions, completions[1:])]
            if intervals:
                jitter_values.append(max(intervals) - min(intervals))

    return {
        "hard_deadline_miss_rate": round(0.0 if not hard_jobs else len(hard_misses) / len(hard_jobs), 6),
        "hard_deadline_miss_count": len(hard_misses),
        "hard_deadline_job_count": len(hard_jobs),
        "soft_deadline_miss_rate": round(soft_deadline_miss_rate, 6),
        "soft_deadline_miss_count": len(soft_misses),
        "soft_deadline_job_count": len(aperiodic_log),
        "average_tardiness": round(mean(tardiness_values), 6) if tardiness_values else 0.0,
        "max_tardiness": max(tardiness_values) if tardiness_values else 0,
        "average_aperiodic_tardiness": round(mean(aperiodic_tardiness), 6) if aperiodic_tardiness else 0.0,
        "max_aperiodic_tardiness": max(aperiodic_tardiness) if aperiodic_tardiness else 0,
        "average_response_time": round(mean(response_times), 6) if response_times else 0.0,
        "max_response_time": max(response_times) if response_times else 0,
        "completion_time_jitter": round(mean(jitter_values), 6) if jitter_values else 0.0,
    }


def calculate_acceptance_metrics(acceptance_log: dict[str, Any]) -> dict[str, Any]:
    sporadic_log = acceptance_log.get("sporadic", [])
    total_sporadic_execution = sum(float(item.get("execution_time", 0.0)) for item in sporadic_log)
    completed_sporadic_execution = sum(
        float(item.get("execution_time", 0.0))
        for item in sporadic_log
        if item.get("accepted", False)
    )
    return {
        "acceptance_test": {
            "sporadic_total": len(sporadic_log),
            "sporadic_accepted": sum(1 for item in sporadic_log if item.get("accepted", False)),
            "sporadic_rejected": sum(1 for item in sporadic_log if not item.get("accepted", False)),
            "aperiodic_total": len(acceptance_log.get("aperiodic", [])),
            "aperiodic_missed": sum(1 for item in acceptance_log.get("aperiodic", []) if item.get("miss", False)),
        },
        "sporadic_value_rate": round(
            0.0 if total_sporadic_execution == 0
            else completed_sporadic_execution / total_sporadic_execution,
            6,
        ),
        "post_acceptance_violation_rate": 0.0,
    }


def price_by_hour(price_data: dict[str, Any]) -> dict[int, float]:
    return {int(row["hour"]): float(row["market_price"]) for row in price_data.get("price", [])}


def calculate_costs(
    schedule_rows: list[dict[str, Any]],
    processor_settings: dict[str, Any],
    price_data: dict[str, Any],
    soft_miss_count: int,
) -> dict[str, float]:
    generators = {
        item["generator_id"]: item
        for item in processor_settings.get("generator", [])
    }
    prices = price_by_hour(price_data)
    generator_cost = 0.0
    market_revenue = 0.0

    for row in schedule_rows:
        t = int(row["t"])
        for generator_id, generator in generators.items():
            output = float(row.get("P", {}).get(generator_id, 0.0))
            if output > EPS:
                generator_cost += float(generator["cost_fixed"]) + float(generator["cost_variable"]) * output
        market_revenue += prices.get(t, 0.0) * float(row.get("sell", 0.0))

    objective_value = APERIODIC_MISS_PENALTY * soft_miss_count + generator_cost - market_revenue
    return {
        "generator_cost": round(generator_cost, 6),
        "market_revenue": round(market_revenue, 6),
        "objective_value": round(objective_value, 6),
    }


def renewable_available_by_hour(settings: dict[str, Any]) -> dict[int, dict[str, float]]:
    capacities = {
        item["renewable_id"]: float(item["capacity"])
        for item in settings.get("renewable_capacity", [])
    }
    available = {t: {rid: 0.0 for rid in capacities} for t in range(1, HORIZON + 1)}
    for group in settings.get("renewable_forecast", []):
        for renewable_id, rows in group.items():
            capacity = capacities.get(renewable_id, 0.0)
            for row in rows:
                t = int(row["hour"])
                if 1 <= t <= HORIZON:
                    available[t][renewable_id] = capacity * float(row["pv_forecast"])
    return available


def check_constraints(
    schedule_rows: list[dict[str, Any]],
    processor_settings: dict[str, Any],
) -> dict[str, Any]:
    violations: list[str] = []
    generators = {
        item["generator_id"]: item
        for item in processor_settings.get("generator", [])
    }
    renewable_caps = renewable_available_by_hour(processor_settings)
    storage = {
        item["storage_id"]: item
        for item in processor_settings.get("storage", [])
    }
    charging_job_to_storage = {
        item["job_id"]: item["target_storage"]
        for item in processor_settings.get("charging_jobs", [])
    }
    generation_sources = set(generators) | {
        item["renewable_id"] for item in processor_settings.get("renewable_capacity", [])
    }

    previous_generator_output = {
        gid: float(generator.get("initial_energy", 0.0))
        for gid, generator in generators.items()
    }
    previous_soc = {
        sid: float(item["soc_init"])
        for sid, item in storage.items()
    }

    for row in schedule_rows:
        t = int(row["t"])
        p_values = {key: float(value) for key, value in row.get("P", {}).items()}
        sell = float(row.get("sell", 0.0))
        if sell < -1e-5:
            violations.append(f"hour {t}: sell is negative")

        external_demand = 0.0
        charging_demand = 0.0
        source_usage: dict[str, float] = defaultdict(float)
        charge_by_storage: dict[str, float] = defaultdict(float)

        for job_id, allocation in row.get("k", {}).items():
            amount = sum(float(value) for value in allocation.values())
            for source_id, value in allocation.items():
                source_usage[source_id] += float(value)
            if job_id in charging_job_to_storage:
                charging_demand += amount
                charge_by_storage[charging_job_to_storage[job_id]] += amount
                for source_id in allocation:
                    if source_id not in generation_sources:
                        violations.append(f"hour {t}: charging job {job_id} uses non-generation source {source_id}")
            else:
                external_demand += amount

        supply = sum(p_values.values())
        if abs(supply - external_demand - charging_demand - sell) > 1e-4:
            violations.append(f"hour {t}: energy balance violation")

        for source_id, used in source_usage.items():
            if used > p_values.get(source_id, 0.0) + 1e-5:
                violations.append(f"hour {t}: source {source_id} supplies more than P")

        for gid, generator in generators.items():
            output = p_values.get(gid, 0.0)
            if output > EPS:
                if output < float(generator["output_min"]) - 1e-5:
                    violations.append(f"hour {t}: {gid} below output_min")
                if output > float(generator["output_max"]) + 1e-5:
                    violations.append(f"hour {t}: {gid} above output_max")
            prev = previous_generator_output[gid]
            if output - prev > float(generator["ramp_up_rate"]) + 1e-5:
                violations.append(f"hour {t}: {gid} ramp-up violation")
            if prev - output > float(generator["ramp_down_rate"]) + 1e-5:
                violations.append(f"hour {t}: {gid} ramp-down violation")
            previous_generator_output[gid] = output

        for renewable_id, caps in renewable_caps.get(t, {}).items():
            if p_values.get(renewable_id, 0.0) > caps + 1e-5:
                violations.append(f"hour {t}: {renewable_id} exceeds forecast")

        for sid, item in storage.items():
            discharge = p_values.get(sid, 0.0)
            charge = charge_by_storage.get(sid, 0.0)
            soc = float(row.get("soc", {}).get(sid, previous_soc[sid]))
            if discharge > float(item["discharge_max"]) + 1e-5:
                violations.append(f"hour {t}: {sid} discharge exceeds max")
            if charge > float(item["charge_max"]) + 1e-5:
                violations.append(f"hour {t}: {sid} charge exceeds max")
            if discharge > EPS and charge > EPS:
                violations.append(f"hour {t}: {sid} charges and discharges simultaneously")
            expected_soc = previous_soc[sid] + charge - discharge
            if abs(soc - expected_soc) > 1e-4:
                violations.append(f"hour {t}: {sid} SOC transition violation")
            if soc < float(item["soc_min"]) - 1e-5 or soc > float(item["soc_max"]) + 1e-5:
                violations.append(f"hour {t}: {sid} SOC out of bounds")
            previous_soc[sid] = soc

    return {
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
    }


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()
    parser = argparse.ArgumentParser(description="Evaluate RTSPJT output JSON files.")
    parser.add_argument("--base-dir", type=Path, default=project_root)
    parser.add_argument("--task-set", type=Path, default=None)
    parser.add_argument("--schedule-result", type=Path, default=None)
    parser.add_argument("--acceptance-log", type=Path, default=None)
    parser.add_argument("--processor-settings", type=Path, default=None)
    parser.add_argument("--price", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    task_set_path = args.task_set or base_dir / "output" / "task_set.json"
    schedule_path = args.schedule_result or base_dir / "output" / "schedule_result.json"
    acceptance_path = args.acceptance_log or base_dir / "output" / "acceptance_test_log.json"
    processor_path = args.processor_settings or base_dir / "input" / "processor_settings.json"
    price_path = args.price or base_dir / "input" / "price_72hr.json"
    output_path = args.output or base_dir / "output" / "evaluation_results.json"

    task_set = load_json(task_set_path)
    schedule_data = load_json(schedule_path)
    acceptance_log = load_json(acceptance_path, {"sporadic": [], "aperiodic": [], "summary": {}})
    processor_settings = load_json(processor_path)
    price_data = load_json(price_path)

    jobs = collect_jobs(schedule_data, acceptance_log)
    schedule_rows = schedule_data.get("schedule_result", [])
    deadline_metrics = calculate_deadline_metrics(jobs, acceptance_log)
    acceptance_metrics = calculate_acceptance_metrics(acceptance_log)
    costs = calculate_costs(
        schedule_rows,
        processor_settings,
        price_data,
        soft_miss_count=deadline_metrics["soft_deadline_miss_count"],
    )
    constraint_report = check_constraints(schedule_rows, processor_settings)

    result = {
        **deadline_metrics,
        **acceptance_metrics,
        **costs,
        **constraint_report,
        "periodic_task_count": len(task_set.get("periodic", {})),
        "total_scheduled_jobs": len(jobs),
        "verification_passed": constraint_report["constraint_violation_count"] == 0,
        "source_files": {
            "task_set": str(task_set_path.resolve()),
            "schedule_result": str(schedule_path.resolve()),
            "acceptance_test_log": str(acceptance_path.resolve()),
            "processor_settings": str(processor_path.resolve()),
            "price": str(price_path.resolve()),
        },
    }
    write_json(output_path, result)

    print("=== Evaluator ===")
    print(f"hard deadline miss rate: {result['hard_deadline_miss_rate']}")
    print(f"soft deadline miss rate: {result['soft_deadline_miss_rate']}")
    print(f"average response time: {result['average_response_time']}")
    print(f"average tardiness: {result['average_tardiness']}")
    print(f"sporadic value rate: {result['sporadic_value_rate']}")
    print(f"generator cost: {result['generator_cost']}")
    print(f"market revenue: {result['market_revenue']}")
    print(f"objective value: {result['objective_value']}")
    print(f"constraint violations: {result['constraint_violation_count']}")
    print(f"wrote: {output_path.resolve()}")


if __name__ == "__main__":
    main()
