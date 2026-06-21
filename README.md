# Java Scheduling System

This project uses Java Swing as the input/output UI and keeps the original
Python scheduling core unchanged. Java exports `output/task_set.json`, launches
the Python scheduler through `ProcessBuilder`, and opens the result viewer after
`output/schedule_result.json` is updated.

## Project Structure

- `src/python/`
  - Python scheduling core: `task_generator.py`, `scheduler.py`,
    `advanced_scheduler.py`, and `evaluator.py`
- `src/java/input_ui/`
  - Java task input UI and backend bridge
- `src/java/output_ui/`
  - Java schedule result viewer that reads `output/schedule_result.json`
- `input/`
  - Processor settings and 72-hour price data
- `output/`
  - Generated task set, schedule result, acceptance log, and evaluation result

## Run

Compile the full Java UI:

```powershell
javac src\java\output_ui\org\slf4j\*.java src\java\output_ui\*.java src\java\input_ui\*.java
```

Open the input UI:

```powershell
java -cp src\java\input_ui;src\java\output_ui TaskView
```

On this machine, you can also use the helper script:

```powershell
.\run-ui.ps1
```

Use `Export JSON` to write `output/task_set.json`, or use `Run Schedule` to
export the tasks, run the Python backend, and open the output UI.

If Python is not on PATH, set `PYTHON_EXE` before starting Java:

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
java -cp src\java\input_ui;src\java\output_ui TaskView
```

## Python Commands

```powershell
python src/python/task_generator.py --base-dir .
python src/python/advanced_scheduler.py --base-dir .
python src/python/evaluator.py --base-dir .
```
