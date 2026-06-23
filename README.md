# Java Scheduling System

This project uses Java Swing as the input/output UI and keeps the original
Python scheduling core unchanged. Java exports `output/task_set.json`, launches
the Python scheduler through `ProcessBuilder`, and opens the result viewer after
`output/schedule_result.json` is updated.

## Project Structure

- `input/`
  - Processor settings and 72-hour price data
- `output/`
  - Generated task set, schedule result, acceptance log, and evaluation result
- `input_ui/`
  - Java task input UI and controller
- `output_ui/`
  - Java schedule result viewer that reads `output/schedule_result.json`
- `backend/`
  - Python scheduling core: `task_generator.py`, `scheduler.py`,
    `advanced_scheduler.py`, and `evaluator.py`
- `backend/java/`
  - Java backend bridge, task-set validation, and backend execution logging

## Run

Compile the full Java UI:

```powershell
javac output_ui\org\slf4j\*.java output_ui\*.java backend\java\*.java input_ui\*.java
```

Open the input UI:

```powershell
java -cp input_ui;output_ui;backend\java TaskView
```

On this machine, you can also use the helper script:

```powershell
.\run-ui.ps1
```

Use `Import JSON` to load an existing task set into the Java table, use
`Export JSON` to write `output/task_set.json`, or use `Run Schedule` to export
the current tasks, run the Python backend, and open the output UI.

## Java Backend Validation

Before Java writes `output/task_set.json` or calls the Python scheduler, the
backend validates the full task set in `backend/java/TaskSetValidator.java`.

The validator checks:

- task count must be 6 to 10
- at least 3 different periods are required
- expanded periodic jobs in the 72-hour horizon must be greater than 30
- workload density must be between 0.7 and 0.9
- required execution-time, high-energy, tight-deadline, and non-preemptive task
  distributions must be present
- each task must satisfy release time, period, execution time, deadline, energy
  demand, preemption, frame-bound, and 72-hour horizon rules

## Java Backend Log

Every `Run Schedule` action writes an execution record to
`output/java_backend_log.json`.

The log records:

- execution timestamp and duration
- task count
- whether Java validation passed
- whether the Python scheduler succeeded
- whether expected output files exist
- error message or Python output preview

If Python is not on PATH, set `PYTHON_EXE` before starting Java:

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
java -cp input_ui;output_ui;backend\java TaskView
```

## Python Commands

```powershell
python backend/task_generator.py --base-dir .
python backend/advanced_scheduler.py --base-dir .
python backend/evaluator.py --base-dir .
```
