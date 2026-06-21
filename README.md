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
  - Java task input UI and backend bridge
- `output_ui/`
  - Java schedule result viewer that reads `output/schedule_result.json`
- `backend/`
  - Python scheduling core: `task_generator.py`, `scheduler.py`,
    `advanced_scheduler.py`, and `evaluator.py`

## Run

Compile the full Java UI:

```powershell
javac output_ui\org\slf4j\*.java output_ui\*.java input_ui\*.java
```

Open the input UI:

```powershell
java -cp input_ui;output_ui TaskView
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
java -cp input_ui;output_ui TaskView
```

## Python Commands

```powershell
python backend/task_generator.py --base-dir .
python backend/advanced_scheduler.py --base-dir .
python backend/evaluator.py --base-dir .
```
