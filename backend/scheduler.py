#!/usr/bin/env python3
"""Level 1 scheduler for the RTSPJT assignment.

The scheduler reads output/task_set.json, fixes frame size at 4, schedules all
periodic jobs inside the 72-hour horizon, and then builds a feasible VPP energy
dispatch using processor_settings.json and price_72hr.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any


HORIZON = 72
FRAME_SIZE = 4
NUM_FRAMES = HORIZON // FRAME_SIZE
EPS = 1e-7
SPORADIC_RESERVE_RATIO = 0.08
SPORADIC_RESERVE_MAX = 12.0
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
        if (candidate / "input").is_dir() and (candidate / "backend").is_dir():
            return candidate
    return current_path.parent.parent.parent


@dataclass(frozen=True)
class Task:
    task_id: str
    release_time: int
    period: int
    execution_time: int
    deadline: int
    energy: float
    preemptive: int


@dataclass
class Job:
    job_id: str
    task_id: str
    release_time: int
    absolute_deadline: int
    execution_time: int
    energy: float
    preemptive: int
    job_type: str = "periodic"
    scheduled_times: list[int] = field(default_factory=list)

    @property
    def completion_time(self) -> int | None:
        return max(self.scheduled_times) if self.scheduled_times else None


def frame_id(t: int) -> int:
    return math.ceil(t / FRAME_SIZE)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_task_set(path: Path) -> list[Task]:
    data = load_json(path)
    tasks: list[Task] = []

    if "periodic" in data:
        for task_id, info in data["periodic"].items():
            tasks.append(
                Task(
                    task_id=task_id,
                    release_time=int(info["r"]),
                    period=int(info["p"]),
                    execution_time=int(info["e"]),
                    deadline=int(info["d"]),
                    energy=float(info["w"]),
                    preemptive=int(info.get("preempt", 1)),
                )
            )
        return tasks

    if "tasks" in data:
        for info in data["tasks"]:
            tasks.append(
                Task(
                    task_id=str(info.get("task_id", info.get("id"))),
                    release_time=int(info.get("release_time", info.get("r"))),
                    period=int(info.get("period", info.get("p"))),
                    execution_time=int(info.get("execution_time", info.get("e"))),
                    deadline=int(info.get("deadline", info.get("relative_deadline", info.get("d")))),
                    energy=float(info.get("energy", info.get("w"))),
                    preemptive=int(info.get("preemptive", info.get("preempt", 1))),
                )
            )
        return tasks

    raise ValueError("task_set.json must contain either a 'periodic' object or a 'tasks' array")

def iter_extra_job_items(section: Any):
    if isinstance(section, dict):
        for job_id, info in section.items():
            yield job_id, info
    elif isinstance(section, list):
        for info in section:
            yield info.get("job_id", info.get("id")), info


def load_extra_jobs(path: Path) -> tuple[list[Job], list[Job]]:
    data = load_json(path) if path.exists() else DEFAULT_EXTRA_JOBS
    sporadic_jobs = []
    aperiodic_jobs = []

    for job_id, info in iter_extra_job_items(data.get("sporadic", [])):
        r = int(info["r"])
        d = int(info["d"])
        sporadic_jobs.append(
            Job(
                job_id=str(job_id),
                task_id=str(job_id),
                release_time=r,
                absolute_deadline=r + d - 1,
                execution_time=int(info["e"]),
                energy=float(info["w"]),
                preemptive=int(info.get("preempt", 1)),
                job_type="sporadic",
            )
        )

    for job_id, info in iter_extra_job_items(data.get("aperiodic", [])):
        r = int(info["r"])
        d = int(info["d"])
        aperiodic_jobs.append(
            Job(
                job_id=str(job_id),
                task_id=str(job_id),
                release_time=r,
                absolute_deadline=r + d - 1,
                execution_time=int(info["e"]),
                energy=float(info["w"]),
                preemptive=int(info.get("preempt", 1)),
                job_type="aperiodic",
            )
        )

    return sporadic_jobs, aperiodic_jobs

def validate_frame(tasks: list[Task]) -> list[str]:
    errors: list[str] = []
    if HORIZON % FRAME_SIZE != 0:
        errors.append(f"HORIZON={HORIZON} is not divisible by frame size {FRAME_SIZE}")
    if tasks and FRAME_SIZE < max(task.execution_time for task in tasks):
        errors.append("frame size must be >= max execution time")
    for task in tasks:
        bound = 2 * FRAME_SIZE - math.gcd(FRAME_SIZE, task.period)
        if bound > task.deadline:
            errors.append(
                f"{task.task_id}: 2f-gcd(f,p)={bound} exceeds relative deadline {task.deadline}"
            )
    return errors


def expand_periodic_jobs(tasks: list[Task]) -> tuple[list[Job], list[dict[str, Any]]]:
    jobs: list[Job] = []
    skipped: list[dict[str, Any]] = []

    for task in tasks:
        instance = 1
        release = task.release_time
        while release <= HORIZON:
            absolute_deadline = release + task.deadline - 1
            job_id = f"{task.task_id}_{instance}"
            if absolute_deadline <= HORIZON:
                jobs.append(
                    Job(
                        job_id=job_id,
                        task_id=task.task_id,
                        release_time=release,
                        absolute_deadline=absolute_deadline,
                        execution_time=task.execution_time,
                        energy=task.energy,
                        preemptive=task.preemptive,
                    )
                )
            else:
                skipped.append(
                    {
                        "job_id": job_id,
                        "task_id": task.task_id,
                        "release_time": release,
                        "absolute_deadline": absolute_deadline,
                        "reason": "deadline exceeds the 72-hour scheduling horizon",
                    }
                )
            instance += 1
            release = task.release_time + (instance - 1) * task.period

    jobs.sort(key=lambda j: (j.absolute_deadline, j.release_time, j.job_id))
    return jobs, skipped


def renewable_available_by_hour(settings: dict[str, Any]) -> dict[int, dict[str, float]]:
    capacities = {
        item["renewable_id"]: float(item["capacity"])
        for item in settings.get("renewable_capacity", [])
    }
    available = {t: {rid: 0.0 for rid in capacities} for t in range(1, HORIZON + 1)}
    for forecast_group in settings.get("renewable_forecast", []):
        for renewable_id, rows in forecast_group.items():
            capacity = capacities.get(renewable_id, 0.0)
            for row in rows:
                t = int(row["hour"])
                if 1 <= t <= HORIZON:
                    available[t][renewable_id] = round(capacity * float(row["pv_forecast"]), 6)
    return available


def price_by_hour(price_data: dict[str, Any]) -> dict[int, float]:
    return {int(row["hour"]): float(row["market_price"]) for row in price_data.get("price", [])}


def hour_scores(settings: dict[str, Any], price_data: dict[str, Any]) -> dict[int, float]:
    renew = renewable_available_by_hour(settings)
    prices = price_by_hour(price_data)
    max_renew = max((sum(v.values()) for v in renew.values()), default=1.0) or 1.0
    max_price = max(prices.values(), default=1.0) or 1.0
    scores: dict[int, float] = {}
    for t in range(1, HORIZON + 1):
        price_norm = prices.get(t, 0.0) / max_price
        renewable_norm = sum(renew[t].values()) / max_renew
        scores[t] = 0.65 * price_norm - 0.35 * renewable_norm
    return scores


def reserve_by_hour(load_capacity: dict[int, float]) -> dict[int, float]:
    return {
        t: min(SPORADIC_RESERVE_MAX, max(0.0, load_capacity[t] * SPORADIC_RESERVE_RATIO))
        for t in range(1, HORIZON + 1)
    }


def candidate_allocations(job: Job, scores: dict[int, float]) -> list[tuple[int, ...]]:
    window = list(range(job.release_time, job.absolute_deadline + 1))
    if len(window) < job.execution_time:
        return []

    if job.preemptive == 0:
        candidates = [
            tuple(range(start, start + job.execution_time))
            for start in range(job.release_time, job.absolute_deadline - job.execution_time + 2)
        ]
    else:
        candidates = list(itertools.combinations(window, job.execution_time))

    def score(times: tuple[int, ...]) -> tuple[float, int, int]:
        energy_cost = sum(scores[t] for t in times) * job.energy
        response_hint = max(times) - job.release_time
        return (energy_cost + 0.01 * response_hint, max(times), times[0])

    candidates.sort(key=score)
    return candidates


def hourly_load_capacity(settings: dict[str, Any]) -> dict[int, float]:
    renew = renewable_available_by_hour(settings)
    thermal_max = sum(float(item["output_max"]) for item in settings.get("generator", []))
    discharge_max = sum(float(item["discharge_max"]) for item in settings.get("storage", []))
    capacity: dict[int, float] = {}
    for t in range(1, HORIZON + 1):
        raw_capacity = thermal_max + discharge_max + sum(renew[t].values())
        capacity[t] = max(30.0, raw_capacity * 0.8)
    return capacity


def solve_job_times(
    jobs: list[Job],
    scores: dict[int, float],
    load_capacity: dict[int, float],
) -> tuple[bool, list[Job], list[dict[str, Any]]]:
    all_candidates = {job.job_id: candidate_allocations(job, scores) for job in jobs}
    failed = [
        {
            "job_id": job.job_id,
            "task_id": job.task_id,
            "release_time": job.release_time,
            "absolute_deadline": job.absolute_deadline,
            "execution_time": job.execution_time,
            "reason": "no candidate time slots",
        }
        for job in jobs
        if not all_candidates[job.job_id]
    ]
    if failed:
        return False, jobs, failed

    job_by_id = {job.job_id: job for job in jobs}
    unscheduled = {job.job_id for job in jobs}
    assignment: dict[str, tuple[int, ...]] = {}
    load_by_hour = {t: 0.0 for t in range(1, HORIZON + 1)}

    def feasible_for(job_id: str) -> list[tuple[int, ...]]:
        job = job_by_id[job_id]
        return [
            cand
            for cand in all_candidates[job_id]
            if all(load_by_hour[t] + job.energy <= load_capacity[t] + EPS for t in cand)
        ]

    def search() -> bool:
        if not unscheduled:
            return True

        choices: list[tuple[int, int, str, list[tuple[int, ...]]]] = []
        for job_id in unscheduled:
            feasible = feasible_for(job_id)
            if not feasible:
                return False
            job = job_by_id[job_id]
            choices.append((len(feasible), job.absolute_deadline, job_id, feasible))

        _, _, selected_id, selected_candidates = min(choices)
        unscheduled.remove(selected_id)
        for cand in selected_candidates:
            assignment[selected_id] = cand
            selected_job = job_by_id[selected_id]
            for t in cand:
                load_by_hour[t] += selected_job.energy
            if search():
                return True
            for t in cand:
                load_by_hour[t] -= selected_job.energy
            assignment.pop(selected_id, None)
        unscheduled.add(selected_id)
        return False

    success = search()
    if not success:
        return False, jobs, [{"reason": "no feasible one-job-per-hour assignment found"}]

    for job in jobs:
        job.scheduled_times = list(assignment[job.job_id])
    jobs.sort(key=lambda j: (min(j.scheduled_times), j.job_id))
    return True, jobs, []

def scheduled_load_by_hour(jobs: list[Job]) -> dict[int, float]:
    load = {t: 0.0 for t in range(1, HORIZON + 1)}
    for job in jobs:
        for t in job.scheduled_times:
            load[t] += job.energy
    return load


def insert_job_without_moving_existing(
    job: Job,
    accepted_jobs: list[Job],
    scores: dict[int, float],
    load_capacity: dict[int, float],
    reserve: dict[int, float] | None = None,
) -> tuple[bool, list[int], str]:
    load = scheduled_load_by_hour(accepted_jobs)
    candidates = candidate_allocations(job, scores)

    if reserve is not None:
        for candidate in candidates:
            if all(load[t] + job.energy <= load_capacity[t] - reserve.get(t, 0.0) + EPS for t in candidate):
                return True, list(candidate), "accepted: feasible before deadline while preserving reserve"

    for candidate in candidates:
        if all(load[t] + job.energy <= load_capacity[t] + EPS for t in candidate):
            return True, list(candidate), "accepted: feasible before deadline using reserve capacity"
    return False, [], "rejected: no feasible slot before deadline without moving existing jobs"


def build_running_by_hour(jobs: list[Job]) -> dict[int, list[str]]:
    running = {t: [] for t in range(1, HORIZON + 1)}
    for job in jobs:
        for t in job.scheduled_times:
            running[t].append(job.job_id)
    return running


def plan_batteries_and_residual_load(
    jobs: list[Job],
    settings: dict[str, Any],
) -> tuple[dict[int, dict[str, float]], dict[int, dict[str, float]], dict[int, float]]:
    renew = renewable_available_by_hour(settings)
    storage = settings.get("storage", [])
    soc = {item["storage_id"]: float(item["soc_init"]) for item in storage}
    soc_min = {item["storage_id"]: float(item["soc_min"]) for item in storage}
    soc_max = {item["storage_id"]: float(item["soc_max"]) for item in storage}
    discharge_max = {item["storage_id"]: float(item["discharge_max"]) for item in storage}
    charge_max = {item["storage_id"]: float(item["charge_max"]) for item in storage}

    load_by_hour = {t: 0.0 for t in range(1, HORIZON + 1)}
    for job in jobs:
        for t in job.scheduled_times:
            load_by_hour[t] += job.energy

    discharge_plan = {t: {sid: 0.0 for sid in soc} for t in range(1, HORIZON + 1)}
    charge_plan = {t: {sid: 0.0 for sid in soc} for t in range(1, HORIZON + 1)}
    residual_for_thermal = {t: 0.0 for t in range(1, HORIZON + 1)}

    for t in range(1, HORIZON + 1):
        renewable_total = sum(renew[t].values())
        residual = max(0.0, load_by_hour[t] - renewable_total)

        for sid in sorted(soc, key=lambda x: soc[x] - soc_min[x], reverse=True):
            amount = min(residual, discharge_max[sid], max(0.0, soc[sid] - soc_min[sid]))
            if amount > EPS:
                discharge_plan[t][sid] = round(amount, 6)
                soc[sid] -= amount
                residual -= amount
            if residual <= EPS:
                break

        residual_for_thermal[t] = round(max(0.0, residual), 6)

        renewable_surplus = max(0.0, renewable_total - load_by_hour[t])
        if residual_for_thermal[t] <= EPS and renewable_surplus > EPS:
            for sid in sorted(soc, key=lambda x: soc_max[x] - soc[x], reverse=True):
                amount = min(renewable_surplus, charge_max[sid], max(0.0, soc_max[sid] - soc[sid]))
                if amount > EPS:
                    charge_plan[t][sid] = round(amount, 6)
                    soc[sid] += amount
                    renewable_surplus -= amount
                if renewable_surplus <= EPS:
                    break

    return discharge_plan, charge_plan, residual_for_thermal


def generator_candidates(
    gen: dict[str, Any],
    prev_p: int,
    prev_duration: int,
    demand_hint: float,
) -> list[tuple[int, int]]:
    output_min = int(gen["output_min"])
    output_max = int(gen["output_max"])
    ramp_up = int(gen["ramp_up_rate"])
    ramp_down = int(gen["ramp_down_rate"])
    min_up = int(gen["min_up_time"])
    min_down = int(gen["min_down_time"])
    prev_on = prev_p > 0

    low = max(0, prev_p - ramp_down)
    high = min(output_max, prev_p + ramp_up)
    demand_point = int(math.ceil(demand_hint))

    useful_outputs = {
        0,
        output_min,
        output_max,
        prev_p,
        low,
        high,
        max(output_min, min(output_max, demand_point)),
    }
    useful_outputs = {p for p in useful_outputs if low <= p <= high}

    if prev_on:
        candidates = []
        if prev_duration >= min_up and 0 in useful_outputs:
            candidates.append((0, 1))
        for p in sorted(useful_outputs):
            if p >= output_min:
                candidates.append((p, min(prev_duration + 1, min_up)))
    else:
        candidates = [(0, min(prev_duration + 1, min_down))]
        if prev_duration >= min_down:
            for p in sorted(useful_outputs):
                if p < output_min:
                    continue
                candidates.append((p, 1))

    return sorted(set(candidates))


def solve_thermal_dispatch(
    settings: dict[str, Any],
    prices: dict[int, float],
    residual_load: dict[int, float],
) -> dict[int, dict[str, float]]:
    generators = settings.get("generator", [])
    if not generators:
        if any(v > EPS for v in residual_load.values()):
            raise RuntimeError("thermal generation is required, but no generators are configured")
        return {t: {} for t in range(1, HORIZON + 1)}

    initial_state = []
    for gen in generators:
        initial_p = int(gen.get("initial_energy", 0))
        if initial_p > 0:
            duration = int(gen.get("initial_on_time", 0))
        else:
            duration = int(gen.get("initial_off_time", 0))
        initial_state.extend([initial_p, duration])

    states: dict[tuple[int, ...], tuple[float, list[tuple[int, ...]]]] = {tuple(initial_state): (0.0, [])}

    for t in range(1, HORIZON + 1):
        next_states: dict[tuple[int, ...], tuple[float, list[tuple[int, ...]]]] = {}
        demand = residual_load[t]
        price = prices.get(t, 0.0)

        for state, (cost_so_far, history) in states.items():
            per_generator_options = []
            for index, gen in enumerate(generators):
                prev_p = state[index * 2]
                prev_duration = state[index * 2 + 1]
                per_generator_options.append(generator_candidates(gen, prev_p, prev_duration, demand))

            for combo in itertools.product(*per_generator_options):
                outputs = [item[0] for item in combo]
                total_output = sum(outputs)
                if total_output + EPS < demand:
                    continue

                next_state_values: list[int] = []
                step_cost = 0.0
                for gen, (p, duration) in zip(generators, combo):
                    next_state_values.extend([p, duration])
                    if p > 0:
                        step_cost += float(gen["cost_fixed"]) + float(gen["cost_variable"]) * p
                surplus = max(0.0, total_output - demand)
                step_cost -= price * surplus
                next_state = tuple(next_state_values)
                new_cost = cost_so_far + step_cost
                old = next_states.get(next_state)
                if old is None or new_cost < old[0]:
                    next_states[next_state] = (new_cost, history + [next_state])

        if not next_states:
            raise RuntimeError(f"no feasible thermal dispatch at hour {t}, demand={demand}")

        if len(next_states) > 5000:
            states = dict(sorted(next_states.items(), key=lambda item: item[1][0])[:5000])
        else:
            states = next_states

    best_state = min(states.values(), key=lambda item: item[0])
    best_history = best_state[1]
    dispatch: dict[int, dict[str, float]] = {}
    for t, state in enumerate(best_history, start=1):
        dispatch[t] = {
            gen["generator_id"]: float(state[index * 2])
            for index, gen in enumerate(generators)
        }
    return dispatch


def take_from_sources(amount: float, sources: dict[str, float]) -> dict[str, float]:
    allocation: dict[str, float] = {}
    remaining = amount
    for source_id in list(sources):
        if remaining <= EPS:
            break
        take = min(remaining, sources[source_id])
        if take > EPS:
            allocation[source_id] = round(take, 6)
            sources[source_id] = round(sources[source_id] - take, 6)
            remaining -= take
    if remaining > 1e-5:
        raise RuntimeError(f"insufficient source energy while allocating job demand: missing {remaining:.6f}")
    return allocation


def build_schedule_result(
    jobs: list[Job],
    settings: dict[str, Any],
    price_data: dict[str, Any],
    skipped_jobs: list[dict[str, Any]],
    failed_jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    renew = renewable_available_by_hour(settings)
    prices = price_by_hour(price_data)
    running_by_hour = build_running_by_hour(jobs)
    job_by_id = {job.job_id: job for job in jobs}

    discharge_plan, charge_plan, residual_load = plan_batteries_and_residual_load(jobs, settings)
    thermal_dispatch = solve_thermal_dispatch(settings, prices, residual_load)

    storage = settings.get("storage", [])
    soc = {item["storage_id"]: float(item["soc_init"]) for item in storage}
    charging_job_by_storage = {
        item["target_storage"]: item["job_id"]
        for item in settings.get("charging_jobs", [])
    }

    schedule_rows = []
    generator_ids = [item["generator_id"] for item in settings.get("generator", [])]
    renewable_ids = [item["renewable_id"] for item in settings.get("renewable_capacity", [])]
    storage_ids = [item["storage_id"] for item in storage]

    for t in range(1, HORIZON + 1):
        p_values: dict[str, float] = {}
        for gid in generator_ids:
            p_values[gid] = round(thermal_dispatch[t].get(gid, 0.0), 6)
        for rid in renewable_ids:
            p_values[rid] = round(renew[t].get(rid, 0.0), 6)
        for sid in storage_ids:
            p_values[sid] = round(discharge_plan[t].get(sid, 0.0), 6)

        source_order = renewable_ids + storage_ids + generator_ids
        external_sources = {source_id: p_values[source_id] for source_id in source_order}
        k_values: dict[str, dict[str, float]] = {}

        for job_id in running_by_hour[t]:
            allocation = take_from_sources(job_by_id[job_id].energy, external_sources)
            k_values[job_id] = allocation

        charge_sources = {source_id: external_sources[source_id] for source_id in renewable_ids + generator_ids}
        total_charge = 0.0
        for sid in storage_ids:
            charge_amount = charge_plan[t].get(sid, 0.0)
            discharge_amount = discharge_plan[t].get(sid, 0.0)
            if charge_amount > EPS and discharge_amount > EPS:
                raise RuntimeError(f"{sid} charges and discharges at hour {t}")
            if charge_amount > EPS:
                job_id = charging_job_by_storage.get(sid, f"{sid}_chg")
                allocation = take_from_sources(charge_amount, charge_sources)
                k_values[job_id] = allocation
                total_charge += charge_amount
                soc[sid] += charge_amount
            if discharge_amount > EPS:
                soc[sid] -= discharge_amount

        # Reflect charging allocations in the shared external source pool.
        for source_id in charge_sources:
            external_sources[source_id] = charge_sources[source_id]

        total_supply = sum(p_values.values())
        external_load = sum(job_by_id[job_id].energy for job_id in running_by_hour[t])
        sell = round(total_supply - external_load - total_charge, 6)
        if sell < -1e-5:
            raise RuntimeError(f"negative sell at hour {t}: {sell}")
        sell = max(0.0, sell)

        schedule_rows.append(
            {
                "t": t,
                "frame_id": frame_id(t),
                "running_jobs": running_by_hour[t],
                "P": p_values,
                "k": k_values,
                "sell": sell,
                "soc": {sid: round(soc[sid], 6) for sid in storage_ids},
                "missed_aperiodic": [],
                "rejected_sporadic": [],
            }
        )

    metrics = build_metrics(jobs, schedule_rows, settings, prices)
    return {
        "frame_size": FRAME_SIZE,
        "num_frames": NUM_FRAMES,
        "schedule_result": schedule_rows,
        "job_schedule": build_job_schedule(jobs),
        "summary": {
            "total_periodic_jobs_in_horizon": len([job for job in jobs if job.job_type == "periodic"]),
            "total_jobs_in_schedule": len(jobs),
            "scheduled_jobs": len([job for job in jobs if job.scheduled_times]),
            "failed_jobs": len(failed_jobs),
            "skipped_jobs_past_horizon": len(skipped_jobs),
            "all_periodic_jobs_scheduled": not failed_jobs and all(job.scheduled_times for job in jobs),
            **metrics,
        },
        "failed_jobs": failed_jobs,
        "skipped_jobs": skipped_jobs,
    }


def build_job_schedule(jobs: list[Job]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for job in sorted(jobs, key=lambda item: (item.release_time, item.job_id)):
        completion = job.completion_time
        rows.append(
            {
                "job_id": job.job_id,
                "task_id": job.task_id,
                "release_time": job.release_time,
                "absolute_deadline": job.absolute_deadline,
                "execution_time": job.execution_time,
                "energy": job.energy,
                "preemptive": job.preemptive,
                "scheduled_times": job.scheduled_times,
                "completion_time": completion,
                "response_time": None if completion is None else completion - job.release_time,
                "deadline_met": completion is not None and completion <= job.absolute_deadline,
            }
        )
    return rows


def build_metrics(
    jobs: list[Job],
    schedule_rows: list[dict[str, Any]],
    settings: dict[str, Any],
    prices: dict[int, float],
) -> dict[str, Any]:
    completed = [job for job in jobs if job.completion_time is not None]
    hard_completed = [job for job in completed if job.job_type in ("periodic", "sporadic")]
    deadline_misses = [
        job for job in hard_completed
        if job.completion_time is not None and job.completion_time > job.absolute_deadline
    ]
    response_times = [job.completion_time - job.release_time for job in completed if job.completion_time is not None]
    tardiness = [
        max(0, (job.completion_time or 0) - job.absolute_deadline)
        for job in completed
    ]

    jitter_values = []
    for task_id in sorted({job.task_id for job in completed}):
        task_jobs = sorted([job for job in completed if job.task_id == task_id], key=lambda j: j.release_time)
        completions = [job.completion_time for job in task_jobs if job.completion_time is not None]
        if len(completions) >= 2:
            intervals = [b - a for a, b in zip(completions, completions[1:])]
            if intervals:
                jitter_values.append(max(intervals) - min(intervals))

    generator_by_id = {item["generator_id"]: item for item in settings.get("generator", [])}
    generator_cost = 0.0
    market_revenue = 0.0
    for row in schedule_rows:
        t = row["t"]
        for gid, gen in generator_by_id.items():
            p = float(row["P"].get(gid, 0.0))
            if p > EPS:
                generator_cost += float(gen["cost_fixed"]) + float(gen["cost_variable"]) * p
        market_revenue += prices.get(t, 0.0) * float(row["sell"])

    hard_total = len([job for job in jobs if job.job_type in ("periodic", "sporadic")])
    hard_miss_rate = 0.0 if hard_total == 0 else len(deadline_misses) / hard_total
    objective_value = generator_cost - market_revenue
    return {
        "hard_deadline_miss_rate": round(hard_miss_rate, 6),
        "average_response_time": round(mean(response_times), 6) if response_times else 0.0,
        "max_response_time": max(response_times) if response_times else 0,
        "average_tardiness": round(mean(tardiness), 6) if tardiness else 0.0,
        "max_tardiness": max(tardiness) if tardiness else 0,
        "completion_time_jitter": round(mean(jitter_values), 6) if jitter_values else 0.0,
        "generator_cost": round(generator_cost, 6),
        "market_revenue": round(market_revenue, 6),
        "objective_value": round(objective_value, 6),
    }


def verify_schedule(jobs: list[Job], rows: list[dict[str, Any]], settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    job_by_id = {job.job_id: job for job in jobs}
    for job in jobs:
        if len(job.scheduled_times) != job.execution_time:
            errors.append(f"{job.job_id}: scheduled {len(job.scheduled_times)} slots, expected {job.execution_time}")
        if any(t < job.release_time for t in job.scheduled_times):
            errors.append(f"{job.job_id}: scheduled outside release/deadline window")
        if job.job_type in ("periodic", "sporadic") and any(
            t > job.absolute_deadline for t in job.scheduled_times
        ):
            errors.append(f"{job.job_id}: hard-deadline job scheduled after deadline")
        if job.preemptive == 0 and job.scheduled_times:
            times = sorted(job.scheduled_times)
            if times != list(range(times[0], times[0] + job.execution_time)):
                errors.append(f"{job.job_id}: non-preemptive job is not contiguous")

    generator_by_id = {item["generator_id"]: item for item in settings.get("generator", [])}
    renewable_caps = {
        item["renewable_id"]: float(item["capacity"])
        for item in settings.get("renewable_capacity", [])
    }
    renewable_caps_by_hour = renewable_available_by_hour(settings)
    storage_by_id = {item["storage_id"]: item for item in settings.get("storage", [])}
    charging_job_to_storage = {
        item["job_id"]: item["target_storage"]
        for item in settings.get("charging_jobs", [])
    }
    generation_source_ids = set(generator_by_id) | set(renewable_caps)
    storage_ids = set(storage_by_id)

    prev_generator_p = {gid: float(gen.get("initial_energy", 0.0)) for gid, gen in generator_by_id.items()}
    generator_status_history = {
        gid: [1 if float(gen.get("initial_energy", 0.0)) > EPS else 0]
        for gid, gen in generator_by_id.items()
    }
    prev_soc = {sid: float(item["soc_init"]) for sid, item in storage_by_id.items()}

    for row in rows:
        t = row["t"]
        supply = sum(float(v) for v in row["P"].values())
        demand = 0.0
        source_usage = {source_id: 0.0 for source_id in row["P"]}
        charge_by_storage = {sid: 0.0 for sid in storage_by_id}
        for job_id, allocation in row["k"].items():
            amount = sum(float(v) for v in allocation.values())
            for source_id, value in allocation.items():
                source_usage[source_id] = source_usage.get(source_id, 0.0) + float(value)

            if job_id in charging_job_to_storage:
                target_storage = charging_job_to_storage[job_id]
                charge_by_storage[target_storage] += amount
                for source_id in allocation:
                    if source_id not in generation_source_ids:
                        errors.append(f"hour {t}: charging job {job_id} is supplied by non-generation source {source_id}")
            else:
                demand += amount
                if job_id in job_by_id:
                    expected = job_by_id[job_id].energy
                    if abs(amount - expected) > 1e-4:
                        errors.append(f"hour {t}: {job_id} receives {amount}, expected {expected}")

        charge = sum(charge_by_storage.values())
        if abs(supply - demand - charge - float(row["sell"])) > 1e-4:
            errors.append(f"hour {t}: energy balance violation")

        if float(row["sell"]) < -1e-5:
            errors.append(f"hour {t}: sell is negative")

        for gid, gen in generator_by_id.items():
            p = float(row["P"].get(gid, 0.0))
            if p > EPS:
                if p < float(gen["output_min"]) - 1e-5 or p > float(gen["output_max"]) + 1e-5:
                    errors.append(f"hour {t}: {gid} output outside min/max bounds")
            prev_p = prev_generator_p[gid]
            if p - prev_p > float(gen["ramp_up_rate"]) + 1e-5:
                errors.append(f"hour {t}: {gid} violates ramp-up limit")
            if prev_p - p > float(gen["ramp_down_rate"]) + 1e-5:
                errors.append(f"hour {t}: {gid} violates ramp-down limit")
            prev_generator_p[gid] = p
            generator_status_history[gid].append(1 if p > EPS else 0)

        for rid in renewable_caps:
            p = float(row["P"].get(rid, 0.0))
            cap = renewable_caps_by_hour[t].get(rid, 0.0)
            if p < -1e-5 or p > cap + 1e-5:
                errors.append(f"hour {t}: {rid} output exceeds renewable forecast cap")

        for source_id, used in source_usage.items():
            p = float(row["P"].get(source_id, 0.0))
            if source_id in generation_source_ids and used > p + 1e-5:
                errors.append(f"hour {t}: {source_id} supplies more k than P")
            if source_id in storage_ids:
                external_used = sum(
                    float(value)
                    for job_id, allocation in row["k"].items()
                    if job_id not in charging_job_to_storage
                    for sid, value in allocation.items()
                    if sid == source_id
                )
                if external_used > p + 1e-5:
                    errors.append(f"hour {t}: {source_id} discharges more k than P")

        for sid, value in row["soc"].items():
            settings_row = storage_by_id[sid]
            discharge = float(row["P"].get(sid, 0.0))
            charge_amount = charge_by_storage.get(sid, 0.0)
            if discharge < -1e-5 or discharge > float(settings_row["discharge_max"]) + 1e-5:
                errors.append(f"hour {t}: {sid} discharge exceeds max")
            if charge_amount < -1e-5 or charge_amount > float(settings_row["charge_max"]) + 1e-5:
                errors.append(f"hour {t}: {sid} charge exceeds max")
            if discharge > EPS and charge_amount > EPS:
                errors.append(f"hour {t}: {sid} charges and discharges simultaneously")
            if discharge > prev_soc[sid] - float(settings_row["soc_min"]) + 1e-5:
                errors.append(f"hour {t}: {sid} discharges below minimum SOC reserve")
            expected_soc = prev_soc[sid] + charge_amount - discharge
            if abs(float(value) - expected_soc) > 1e-4:
                errors.append(f"hour {t}: {sid} SOC transition violation")
            if value < float(settings_row["soc_min"]) - 1e-5 or value > float(settings_row["soc_max"]) + 1e-5:
                errors.append(f"hour {t}: {sid} SOC out of bounds")
            prev_soc[sid] = float(value)

    for gid, gen in generator_by_id.items():
        statuses = generator_status_history[gid]
        min_up = int(gen["min_up_time"])
        min_down = int(gen["min_down_time"])
        initial_on = int(gen.get("initial_on_time", 0))
        initial_off = int(gen.get("initial_off_time", 0))
        for index in range(1, len(statuses)):
            if statuses[index - 1] == 0 and statuses[index] == 1:
                if index == 1 and initial_off < min_down:
                    errors.append(f"hour {index}: {gid} starts before initial min-down is satisfied")
                run = 0
                for value in statuses[index:]:
                    if value == 1:
                        run += 1
                    else:
                        break
                if run < min_up and index + run - 1 <= HORIZON:
                    errors.append(f"hour {index}: {gid} violates min-up time")
            if statuses[index - 1] == 1 and statuses[index] == 0:
                if index == 1 and initial_on < min_up:
                    errors.append(f"hour {index}: {gid} stops before initial min-up is satisfied")
                down = 0
                for value in statuses[index:]:
                    if value == 0:
                        down += 1
                    else:
                        break
                if down < min_down and index + down - 1 <= HORIZON:
                    errors.append(f"hour {index}: {gid} violates min-down time")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the 72-hour static schedule_result.json")
    default_base = find_project_root()
    parser.add_argument("--base-dir", type=Path, default=default_base)
    parser.add_argument("--task-set", type=Path, default=None)
    parser.add_argument("--processor-settings", type=Path, default=None)
    parser.add_argument("--price", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--extra-jobs", type=Path, default=None)
    parser.add_argument("--acceptance-log", type=Path, default=None)
    return parser.parse_args()

def run_sporadic_acceptance_test(
    base_jobs: list[Job],
    sporadic_jobs: list[Job],
    scores: dict[int, float],
    load_capacity: dict[int, float],
) -> tuple[list[Job], list[dict[str, Any]]]:
    accepted_jobs = list(base_jobs)
    log = []
    reserve = reserve_by_hour(load_capacity)

    for job in sorted(sporadic_jobs, key=lambda j: (j.release_time, j.absolute_deadline)):
        accepted, times, reason = insert_job_without_moving_existing(
            job,
            accepted_jobs,
            scores,
            load_capacity,
            reserve,
        )

        if accepted:
            job.scheduled_times = times
            accepted_jobs.append(job)

        log.append(
            {
                "job_id": job.job_id,
                "type": "sporadic",
                "release_time": job.release_time,
                "absolute_deadline": job.absolute_deadline,
                "execution_time": job.execution_time,
                "energy": job.energy,
                "accepted": accepted,
                "scheduled_times": times,
                "reason": reason,
            }
        )

    return accepted_jobs, log

def schedule_aperiodic_jobs(
    base_jobs: list[Job],
    aperiodic_jobs: list[Job],
    scores: dict[int, float],
    load_capacity: dict[int, float],
) -> tuple[list[Job], list[dict[str, Any]]]:
    accepted_jobs = list(base_jobs)
    log = []

    for job in sorted(aperiodic_jobs, key=lambda j: (j.release_time, j.absolute_deadline)):
        load = scheduled_load_by_hour(accepted_jobs)

        def make_candidates(end_time: int) -> list[tuple[int, ...]]:
            window = list(range(job.release_time, end_time + 1))
            if len(window) < job.execution_time:
                return []
            if job.preemptive == 0:
                return [
                    tuple(range(start, start + job.execution_time))
                    for start in range(job.release_time, end_time - job.execution_time + 2)
                ]
            return list(itertools.combinations(window, job.execution_time))

        before_deadline = make_candidates(min(job.absolute_deadline, HORIZON))
        before_deadline_set = set(before_deadline)
        after_deadline = [
            candidate
            for candidate in make_candidates(HORIZON)
            if candidate not in before_deadline_set
        ]

        def aperiodic_score(times: tuple[int, ...]) -> tuple[int, int, float, int]:
            completion = max(times)
            tardiness = max(0, completion - job.absolute_deadline)
            laxity = job.absolute_deadline - completion
            return (tardiness, -laxity, sum(scores[t] for t in times), completion)

        candidates = before_deadline + after_deadline
        candidates.sort(key=aperiodic_score)

        selected = []
        for candidate in candidates:
            if all(load[t] + job.energy <= load_capacity[t] + EPS for t in candidate):
                selected = list(candidate)
                break

        if selected:
            job.scheduled_times = selected
            accepted_jobs.append(job)
            completion = max(selected)
            miss = completion > job.absolute_deadline
            tardiness = max(0, completion - job.absolute_deadline)
            reason = "scheduled before soft deadline" if not miss else "scheduled after soft deadline"
        else:
            completion = None
            miss = True
            tardiness = HORIZON - job.absolute_deadline
            reason = "not scheduled within horizon"

        log.append(
            {
                "job_id": job.job_id,
                "type": "aperiodic",
                "release_time": job.release_time,
                "absolute_deadline": job.absolute_deadline,
                "execution_time": job.execution_time,
                "energy": job.energy,
                "scheduled_times": selected,
                "completion_time": completion,
                "miss": miss,
                "tardiness": tardiness,
                "reason": reason,
            }
        )

    return accepted_jobs, log


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir
    task_set_path = args.task_set or base_dir / "output" / "task_set.json"
    processor_path = args.processor_settings or base_dir / "input" / "processor_settings.json"
    price_path = args.price or base_dir / "input" / "price_72hr.json"
    output_path = args.output or base_dir / "output" / "schedule_result.json"
    default_teacher_extra_path = base_dir / "input" / "aperiodic_n_sporadic.json"
    default_extra_jobs_path = base_dir / "input" / "extra_jobs.json"
    extra_jobs_path = args.extra_jobs or (
        default_teacher_extra_path
        if default_teacher_extra_path.exists()
        else default_extra_jobs_path
    )
    acceptance_log_path = args.acceptance_log or base_dir / "output" / "acceptance_test_log.json"

    tasks = load_task_set(task_set_path)
    frame_errors = validate_frame(tasks)
    if frame_errors:
        raise ValueError("Invalid frame size for this task set:\n" + "\n".join(frame_errors))

    settings = load_json(processor_path)
    price_data = load_json(price_path)
    scores = hour_scores(settings, price_data)
    load_capacity = hourly_load_capacity(settings)

    jobs, skipped_jobs = expand_periodic_jobs(tasks)
    success, scheduled_jobs, failed_jobs = solve_job_times(jobs, scores, load_capacity)
    if not success:
        print("WARNING: periodic job search did not find a complete assignment")
    
    sporadic_jobs, aperiodic_jobs = load_extra_jobs(extra_jobs_path)

    all_scheduled_jobs, sporadic_log = run_sporadic_acceptance_test(
        scheduled_jobs,
        sporadic_jobs,
        scores,
        load_capacity,
    )

    all_scheduled_jobs, aperiodic_log = schedule_aperiodic_jobs(
        all_scheduled_jobs,
        aperiodic_jobs,
        scores,
        load_capacity,
    )

    schedule_output = build_schedule_result(
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

    verification_errors = verify_schedule(all_scheduled_jobs, schedule_output["schedule_result"], settings)
    schedule_output["verification"] = {
        "passed": not verification_errors and not failed_jobs,
        "errors": verification_errors,
    }

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

    summary = schedule_output["summary"]

    total_sporadic_execution = sum(item["execution_time"] for item in sporadic_log)
    completed_sporadic_execution = sum(
        item["execution_time"]
        for item in sporadic_log
        if item["accepted"]
    )

    schedule_output["summary"]["sporadic_value_rate"] = (
        0.0 if total_sporadic_execution == 0
        else round(completed_sporadic_execution / total_sporadic_execution, 6)
    )

    schedule_output["summary"]["soft_deadline_miss_rate"] = (
        0.0 if not aperiodic_log
        else round(sum(1 for item in aperiodic_log if item["miss"]) / len(aperiodic_log), 6)
    )

    schedule_output["summary"]["average_aperiodic_tardiness"] = (
        0.0 if not aperiodic_log
        else round(mean(item["tardiness"] for item in aperiodic_log), 6)
    )
    
    acceptance_log_path.parent.mkdir(parents=True, exist_ok=True)
    with acceptance_log_path.open("w", encoding="utf-8") as f:
        json.dump(acceptance_log, f, indent=4, ensure_ascii=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(schedule_output, f, indent=4, ensure_ascii=False)

    



    print("=== Level 1 Scheduler ===")
    print(f"task_set: {task_set_path}")
    print(f"frame_size: {FRAME_SIZE}, frames: {NUM_FRAMES}")
    print(f"periodic jobs in horizon: {summary['total_periodic_jobs_in_horizon']}")
    print(f"scheduled: {summary['scheduled_jobs']}, failed: {summary['failed_jobs']}")
    print(f"verification passed: {schedule_output['verification']['passed']}")
    print(f"average response time: {summary['average_response_time']}")
    print(f"generator cost: {summary['generator_cost']}")
    print(f"market revenue: {summary['market_revenue']}")
    print(f"wrote: {output_path}")


if __name__ == "__main__":
    main()
