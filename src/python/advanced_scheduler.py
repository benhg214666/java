#!/usr/bin/env python3


from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from statistics import mean
from typing import Any


HORIZON = 72
EPS = 1e-7
APERIODIC_MISS_PENALTY = 10_000.0
STORAGE_AGING_COST_PER_MWH = 6.0
SELL_SHORTFALL_PENALTY_PER_MWH = 35.0
DEFAULT_EXTRA_JOBS = {
    "aperiodic": {
        "a1": {"r": 1, "e": 3, "w": 15, "d": 15, "preempt": 1},
        "a2": {"r": 3, "e": 4, "w": 10, "d": 10, "preempt": 1},
        "a3": {"r": 5, "e": 4, "w": 12, "d": 12, "preempt": 0},
    },
    "sporadic": {
        "s1": {"r": 1, "e": 3, "d": 10, "w": 15, "preempt": 1},
        "s2": {"r": 3, "e": 4, "d": 15, "w": 10, "preempt": 1},
    },
}


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def add_src_to_path(base_dir: Path) -> None:
    python_src_dir = base_dir / "src" / "python"
    if str(python_src_dir) not in sys.path:
        sys.path.insert(0, str(python_src_dir))


def renewable_multiplier(hour: int) -> float:
    """Deterministic actual-vs-forecast scenario used for reproducible demos."""
    if 8 <= hour <= 15:
        return 0.72
    if 31 <= hour <= 43:
        return 0.86
    if 56 <= hour <= 66:
        return 0.93
    if hour in {16, 17, 44, 45, 67}:
        return 0.65
    return 1.0


def realtime_price_multiplier(hour: int) -> float:
    if 18 <= hour <= 23 or 42 <= hour <= 47:
        return 1.18
    if 10 <= hour <= 15 or 58 <= hour <= 64:
        return 0.88
    return 1.0


def build_actual_processor_settings(settings: dict[str, Any]) -> dict[str, Any]:
    actual = copy.deepcopy(settings)
    for group in actual.get("renewable_forecast", []):
        for _, rows in group.items():
            for row in rows:
                hour = int(row["hour"])
                forecast = float(row["pv_forecast"])
                row["pv_forecast"] = round(max(0.0, min(1.0, forecast * renewable_multiplier(hour))), 6)
                row["forecast_reference"] = forecast
                row["actual_multiplier"] = renewable_multiplier(hour)
    actual["level2_storage_model"] = {
        "aging_cost_per_mwh_throughput": STORAGE_AGING_COST_PER_MWH,
        "description": "Storage feasibility follows Level 1 SOC limits; Level 2 objective adds throughput aging cost.",
    }
    return actual


def build_realtime_price(price_data: dict[str, Any]) -> dict[str, Any]:
    realtime = {"price": []}
    for row in price_data.get("price", []):
        hour = int(row["hour"])
        forecast_price = float(row["market_price"])
        realtime["price"].append(
            {
                "hour": hour,
                "market_price": round(forecast_price * realtime_price_multiplier(hour), 6),
                "day_ahead_price": forecast_price,
                "realtime_multiplier": realtime_price_multiplier(hour),
            }
        )
    return realtime


def compute_storage_throughput(schedule_rows: list[dict[str, Any]], settings: dict[str, Any]) -> float:
    storage_ids = {item["storage_id"] for item in settings.get("storage", [])}
    charging_jobs = {item["job_id"] for item in settings.get("charging_jobs", [])}
    throughput = 0.0
    for row in schedule_rows:
        throughput += sum(float(row.get("P", {}).get(sid, 0.0)) for sid in storage_ids)
        for job_id, allocation in row.get("k", {}).items():
            if job_id in charging_jobs:
                throughput += sum(float(value) for value in allocation.values())
    return round(throughput, 6)


def compute_sell_shortfall_penalty(
    level1_rows: list[dict[str, Any]],
    level2_rows: list[dict[str, Any]],
) -> tuple[float, float]:
    level1_sell = {int(row["t"]): float(row.get("sell", 0.0)) for row in level1_rows}
    level2_sell = {int(row["t"]): float(row.get("sell", 0.0)) for row in level2_rows}
    shortfall = 0.0
    for hour in range(1, HORIZON + 1):
        shortfall += max(0.0, level1_sell.get(hour, 0.0) - level2_sell.get(hour, 0.0))
    return round(shortfall, 6), round(shortfall * SELL_SHORTFALL_PENALTY_PER_MWH, 6)


def build_dynamic_update_log(
    settings: dict[str, Any],
    actual_settings: dict[str, Any],
    price_data: dict[str, Any],
    realtime_price: dict[str, Any],
) -> list[dict[str, Any]]:
    import scheduler

    forecast_renew = scheduler.renewable_available_by_hour(settings)
    actual_renew = scheduler.renewable_available_by_hour(actual_settings)
    day_price = scheduler.price_by_hour(price_data)
    rt_price = scheduler.price_by_hour(realtime_price)

    log = []
    for hour in range(1, HORIZON + 1):
        forecast_total = sum(forecast_renew[hour].values())
        actual_total = sum(actual_renew[hour].values())
        renewable_gap = forecast_total - actual_total
        price_delta = rt_price.get(hour, 0.0) - day_price.get(hour, 0.0)
        trigger = renewable_gap > 5.0 or abs(price_delta) > 10.0 or hour in {1, 24, 48}
        if trigger:
            reasons = []
            if renewable_gap > 5.0:
                reasons.append("renewable shortfall")
            if abs(price_delta) > 10.0:
                reasons.append("real-time price update")
            if hour in {1, 24, 48}:
                reasons.append("rolling horizon checkpoint")
            log.append(
                {
                    "hour": hour,
                    "forecast_renewable_mwh": round(forecast_total, 6),
                    "actual_renewable_mwh": round(actual_total, 6),
                    "renewable_gap_mwh": round(renewable_gap, 6),
                    "day_ahead_price": day_price.get(hour, 0.0),
                    "realtime_price": rt_price.get(hour, 0.0),
                    "trigger_reasons": reasons,
                    "action": "refresh scores, recompute feasible dispatch, then re-run acceptance decisions for unreleased soft/dynamic jobs",
                }
            )
    return log


def load_extra_jobs(path: Path) -> tuple[list[Any], list[Any]]:
    import scheduler

    if path.exists():
        return scheduler.load_extra_jobs(path)

    sporadic_jobs = []
    aperiodic_jobs = []
    for job_id, info in DEFAULT_EXTRA_JOBS["sporadic"].items():
        release = int(info["r"])
        sporadic_jobs.append(
            scheduler.Job(
                job_id=job_id,
                task_id=job_id,
                release_time=release,
                absolute_deadline=release + int(info["d"]) - 1,
                execution_time=int(info["e"]),
                energy=float(info["w"]),
                preemptive=int(info.get("preempt", 1)),
                job_type="sporadic",
            )
        )
    for job_id, info in DEFAULT_EXTRA_JOBS["aperiodic"].items():
        release = int(info["r"])
        aperiodic_jobs.append(
            scheduler.Job(
                job_id=job_id,
                task_id=job_id,
                release_time=release,
                absolute_deadline=release + int(info["d"]) - 1,
                execution_time=int(info["e"]),
                energy=float(info["w"]),
                preemptive=int(info.get("preempt", 1)),
                job_type="aperiodic",
            )
        )
    return sporadic_jobs, aperiodic_jobs


def build_static_level1_baseline(
    base_dir: Path,
    settings: dict[str, Any],
    price_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    import evaluator
    import scheduler

    task_set_path = base_dir / "output" / "task_set.json"
    extra_jobs_path = base_dir / "input" / "aperiodic_n_sporadic.json"
    tasks = scheduler.load_task_set(task_set_path)
    scores = scheduler.hour_scores(settings, price_data)
    load_capacity = scheduler.hourly_load_capacity(settings)
    jobs, skipped_jobs = scheduler.expand_periodic_jobs(tasks)
    success, scheduled_jobs, failed_jobs = scheduler.solve_job_times(jobs, scores, load_capacity)
    if not success:
        print("WARNING: Level 1 baseline search did not find a complete assignment")

    sporadic_jobs, aperiodic_jobs = load_extra_jobs(extra_jobs_path)
    all_scheduled_jobs, sporadic_log = scheduler.run_sporadic_acceptance_test(
        scheduled_jobs,
        sporadic_jobs,
        scores,
        load_capacity,
    )
    all_scheduled_jobs, aperiodic_log = scheduler.schedule_aperiodic_jobs(
        all_scheduled_jobs,
        aperiodic_jobs,
        scores,
        load_capacity,
    )
    schedule_output = scheduler.build_schedule_result(
        all_scheduled_jobs,
        settings,
        price_data,
        skipped_jobs=skipped_jobs,
        failed_jobs=failed_jobs,
    )

    row_by_t = {row["t"]: row for row in schedule_output["schedule_result"]}
    for item in sporadic_log:
        if not item["accepted"]:
            t = item["release_time"]
            if 1 <= t <= HORIZON:
                row_by_t[t]["rejected_sporadic"].append(item["job_id"])
    for item in aperiodic_log:
        if item["miss"]:
            t = item["absolute_deadline"]
            if 1 <= t <= HORIZON:
                row_by_t[t]["missed_aperiodic"].append(item["job_id"])

    acceptance_log = {
        "sporadic": sporadic_log,
        "aperiodic": aperiodic_log,
        "summary": {
            "sporadic_total": len(sporadic_log),
            "sporadic_accepted": sum(1 for item in sporadic_log if item["accepted"]),
            "aperiodic_total": len(aperiodic_log),
            "aperiodic_missed": sum(1 for item in aperiodic_log if item["miss"]),
        },
    }
    jobs_for_eval = evaluator.collect_jobs(schedule_output, acceptance_log)
    deadline_metrics = evaluator.calculate_deadline_metrics(jobs_for_eval, acceptance_log)
    acceptance_metrics = evaluator.calculate_acceptance_metrics(acceptance_log)
    costs = evaluator.calculate_costs(
        schedule_output["schedule_result"],
        settings,
        price_data,
        soft_miss_count=deadline_metrics["soft_deadline_miss_count"],
    )
    return schedule_output, {**deadline_metrics, **acceptance_metrics, **costs}


def build_evaluation(
    base_dir: Path,
    schedule_output: dict[str, Any],
    acceptance_log: dict[str, Any],
    actual_settings: dict[str, Any],
    realtime_price: dict[str, Any],
    level1_schedule: dict[str, Any],
    level1_eval: dict[str, Any],
) -> dict[str, Any]:
    import evaluator

    jobs = evaluator.collect_jobs(schedule_output, acceptance_log)
    schedule_rows = schedule_output.get("schedule_result", [])
    deadline_metrics = evaluator.calculate_deadline_metrics(jobs, acceptance_log)
    acceptance_metrics = evaluator.calculate_acceptance_metrics(acceptance_log)
    costs = evaluator.calculate_costs(
        schedule_rows,
        actual_settings,
        realtime_price,
        soft_miss_count=deadline_metrics["soft_deadline_miss_count"],
    )
    constraint_report = evaluator.check_constraints(schedule_rows, actual_settings)

    throughput = compute_storage_throughput(schedule_rows, actual_settings)
    storage_aging_cost = round(throughput * STORAGE_AGING_COST_PER_MWH, 6)
    shortfall_mwh, sell_penalty = compute_sell_shortfall_penalty(
        level1_schedule.get("schedule_result", []),
        schedule_rows,
    )
    objective_value = round(
        APERIODIC_MISS_PENALTY * deadline_metrics["soft_deadline_miss_count"]
        + costs["generator_cost"]
        + storage_aging_cost
        + sell_penalty
        - costs["market_revenue"],
        6,
    )

    result = {
        **deadline_metrics,
        **acceptance_metrics,
        **constraint_report,
        "generator_cost": costs["generator_cost"],
        "market_revenue": costs["market_revenue"],
        "storage_throughput_mwh": throughput,
        "storage_aging_cost": storage_aging_cost,
        "sell_commitment_shortfall_mwh": shortfall_mwh,
        "sell_commitment_penalty": sell_penalty,
        "objective_value": objective_value,
        "verification_passed": constraint_report["constraint_violation_count"] == 0,
        "level2_relaxed_assumptions": [
            "actual renewable output may differ from day-ahead forecast",
            "storage aging cost is charged by charge/discharge throughput",
            "real-time market price differs from day-ahead price and sell shortfall has penalty",
        ],
        "comparison_to_level1": {
            "generator_cost_delta": round(costs["generator_cost"] - float(level1_eval.get("generator_cost", 0.0)), 6),
            "market_revenue_delta": round(costs["market_revenue"] - float(level1_eval.get("market_revenue", 0.0)), 6),
            "objective_value_delta": round(objective_value - float(level1_eval.get("objective_value", 0.0)), 6),
            "sporadic_value_rate_delta": round(
                acceptance_metrics["sporadic_value_rate"] - float(level1_eval.get("sporadic_value_rate", 0.0)),
                6,
            ),
            "soft_deadline_miss_rate_delta": round(
                deadline_metrics["soft_deadline_miss_rate"] - float(level1_eval.get("soft_deadline_miss_rate", 0.0)),
                6,
            ),
        },
        "source_files": {
            "base_dir": str(base_dir.resolve()),
            "schedule_result": "output/schedule_result.json",
            "acceptance_test_log": "output/acceptance_test_log.json",
        },
    }
    return result


def run_level2(base_dir: Path) -> dict[str, Any]:
    add_src_to_path(base_dir)
    import scheduler

    task_set_path = base_dir / "output" / "task_set.json"
    settings_path = base_dir / "input" / "processor_settings.json"
    price_path = base_dir / "input" / "price_72hr.json"
    extra_jobs_path = base_dir / "input" / "aperiodic_n_sporadic.json"

    settings = load_json(settings_path)
    price_data = load_json(price_path)
    actual_settings = build_actual_processor_settings(settings)
    realtime_price = build_realtime_price(price_data)
    level1_schedule, level1_eval = build_static_level1_baseline(base_dir, settings, price_data)

    tasks = scheduler.load_task_set(task_set_path)
    frame_errors = scheduler.validate_frame(tasks)
    if frame_errors:
        raise ValueError("Invalid frame size for this task set:\n" + "\n".join(frame_errors))

    scores = scheduler.hour_scores(actual_settings, realtime_price)
    load_capacity = scheduler.hourly_load_capacity(actual_settings)
    jobs, skipped_jobs = scheduler.expand_periodic_jobs(tasks)
    success, scheduled_jobs, failed_jobs = scheduler.solve_job_times(jobs, scores, load_capacity)
    if not success:
        print("WARNING: Level 2 periodic search did not find a complete assignment")

    sporadic_jobs, aperiodic_jobs = load_extra_jobs(extra_jobs_path)
    all_scheduled_jobs, sporadic_log = scheduler.run_sporadic_acceptance_test(
        scheduled_jobs,
        sporadic_jobs,
        scores,
        load_capacity,
    )
    all_scheduled_jobs, aperiodic_log = scheduler.schedule_aperiodic_jobs(
        all_scheduled_jobs,
        aperiodic_jobs,
        scores,
        load_capacity,
    )

    schedule_output = scheduler.build_schedule_result(
        all_scheduled_jobs,
        actual_settings,
        realtime_price,
        skipped_jobs=skipped_jobs,
        failed_jobs=failed_jobs,
    )
    schedule_output["level"] = 2
    schedule_output["dynamic_model"] = {
        "method": "event-triggered rolling refresh with actual renewable output and real-time prices",
        "storage_aging_cost_per_mwh": STORAGE_AGING_COST_PER_MWH,
        "sell_shortfall_penalty_per_mwh": SELL_SHORTFALL_PENALTY_PER_MWH,
    }
    schedule_output["dynamic_update_log"] = build_dynamic_update_log(
        settings,
        actual_settings,
        price_data,
        realtime_price,
    )

    row_by_t = {row["t"]: row for row in schedule_output["schedule_result"]}
    for item in sporadic_log:
        item["level2_policy"] = "hard-deadline acceptance test after refreshing renewable and price state"
        if not item["accepted"]:
            t = item["release_time"]
            if 1 <= t <= HORIZON:
                row_by_t[t]["rejected_sporadic"].append(item["job_id"])

    for item in aperiodic_log:
        item["level2_policy"] = "soft-deadline queue scheduled with refreshed state and price-aware scoring"
        if item["miss"]:
            t = item["absolute_deadline"]
            if 1 <= t <= HORIZON:
                row_by_t[t]["missed_aperiodic"].append(item["job_id"])

    verification_errors = scheduler.verify_schedule(
        all_scheduled_jobs,
        schedule_output["schedule_result"],
        actual_settings,
    )
    schedule_output["verification"] = {
        "passed": not verification_errors and not failed_jobs,
        "errors": verification_errors,
    }

    acceptance_log = {
        "level": 2,
        "sporadic": sporadic_log,
        "aperiodic": aperiodic_log,
        "dynamic_updates": schedule_output["dynamic_update_log"],
        "summary": {
            "sporadic_total": len(sporadic_log),
            "sporadic_accepted": sum(1 for item in sporadic_log if item["accepted"]),
            "aperiodic_total": len(aperiodic_log),
            "aperiodic_missed": sum(1 for item in aperiodic_log if item["miss"]),
            "dynamic_update_count": len(schedule_output["dynamic_update_log"]),
        },
    }

    evaluation = build_evaluation(
        base_dir,
        schedule_output,
        acceptance_log,
        actual_settings,
        realtime_price,
        level1_schedule,
        level1_eval,
    )

    write_json(base_dir / "output" / "schedule_result.json", schedule_output)
    write_json(base_dir / "output" / "acceptance_test_log.json", acceptance_log)
    write_json(base_dir / "output" / "evaluation_results.json", evaluation)
    return evaluation


def parse_args() -> argparse.Namespace:
    default_base = find_project_root()
    parser = argparse.ArgumentParser(description="Run RTSPJT Level 2 advanced dynamic scheduling.")
    parser.add_argument("--base-dir", type=Path, default=default_base)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluation = run_level2(args.base_dir.resolve())
    print("=== Level 2 Advanced Scheduler ===")
    print(f"hard deadline miss rate: {evaluation['hard_deadline_miss_rate']}")
    print(f"soft deadline miss rate: {evaluation['soft_deadline_miss_rate']}")
    print(f"sporadic value rate: {evaluation['sporadic_value_rate']}")
    print(f"generator cost: {evaluation['generator_cost']}")
    print(f"market revenue: {evaluation['market_revenue']}")
    print(f"storage aging cost: {evaluation['storage_aging_cost']}")
    print(f"sell commitment penalty: {evaluation['sell_commitment_penalty']}")
    print(f"objective value: {evaluation['objective_value']}")
    print(f"constraint violations: {evaluation['constraint_violation_count']}")


if __name__ == "__main__":
    main()
