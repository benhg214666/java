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
- `backend/`
  - `java/input_ui/`: Java task input UI and backend bridge
  - `java/output_ui/`: Java schedule result viewer that reads `output/schedule_result.json`
  - `python/`: scheduling core: `task_generator.py`, `scheduler.py`,
    `advanced_scheduler.py`, and `evaluator.py`

## Run

Compile the full Java UI:

```powershell
javac backend\java\output_ui\org\slf4j\*.java backend\java\output_ui\*.java backend\java\input_ui\*.java
```

Open the input UI:

```powershell
java -cp backend\java\input_ui;backend\java\output_ui TaskView
```

On this machine, you can also use the helper script:

```powershell
.\run-ui.ps1
```

Use `Import JSON` to load an existing task set into the Java table, use
`Export JSON` to write `output/task_set.json`, or use `Run Schedule` to export
the current tasks, run the Python backend, and open the output UI.

If Python is not on PATH, set `PYTHON_EXE` before starting Java:

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
java -cp backend\java\input_ui;backend\java\output_ui TaskView
```

## Python Commands

```powershell
python backend/python/task_generator.py --base-dir .
python backend/python/advanced_scheduler.py --base-dir .
python backend/python/evaluator.py --base-dir .
```
