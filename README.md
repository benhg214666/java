# 排程系統專案

這是基於舊有 Python 排程專案上，新增 Java 前後端的期末專案，用於建立與檢視排程結果。

## 專案內容

- `src/python/`
  - 核心排程邏輯與資料產生流程
  - `task_generator.py`、`scheduler.py`、`evaluator.py`
- `src/java/input_ui/`
  - Java 前端輸入介面
- `src/java/output_ui/`
  - Java 輸出檢視介面，顯示 `output/schedule_result.json` 的結果

## 使用方式

- Python 核心
  - `python src/python/task_generator.py --base-dir .`
  - `python src/python/scheduler.py --base-dir .`
  - `python src/python/evaluator.py --base-dir .`
- Java Input UI
  - `javac src\java\input_ui\*.java`
  - `java -cp src\java\input_ui TaskView`
- Java Output UI
  - `javac src\java\output_ui\org\slf4j\*.java src\java\output_ui\*.java`
  - `java -cp src\java\output_ui OutputFrame`

## 目標

將 Python 排程結果輸出成 JSON，並透過 Java UI 進行結果檢視與甘特圖展示。