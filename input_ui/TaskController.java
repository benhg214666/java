import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import javax.swing.SwingWorker;

public class TaskController {

    private TaskInputView view;
    private final BackendService backendService;
    private final TaskSetValidator taskSetValidator;
    private final BackendLogService backendLogService;

    public TaskController(TaskInputView view) {
        this.view = view;
        this.backendService = new BackendService();
        this.taskSetValidator = new TaskSetValidator();
        this.backendLogService = new BackendLogService(backendService.getProjectRoot());
        registerEventListeners();
    }

    private void registerEventListeners() {
        view.onAddButtonClicked(this::handleAddButtonClick);
        view.onDeleteButtonClicked(this::handleDeleteButtonClick);
        view.onImportButtonClicked(this::handleImportButtonClick);
        view.onExportButtonClicked(this::handleExportButtonClick);
        view.onRunScheduleButtonClicked(this::handleRunScheduleButtonClick);
    }

    private void handleAddButtonClick() {
        view.addEmptyRow();
    }

    private void handleDeleteButtonClick() {
        int selectedRowIndex = view.getSelectedRowIndex();

        if (isValidRowIndex(selectedRowIndex)) {
            view.deleteRow(selectedRowIndex);
            return;
        }

        view.showErrorMessage("Please select a row to delete.");
    }

    private void handleExportButtonClick() {
        exportTasksToJsonFile(true);
    }

    private void handleImportButtonClick() {
        Path selectedPath = view.chooseTaskSetJsonFile();
        if (selectedPath == null) {
            return;
        }

        try {
            List<Task> tasks = loadTasksFromJsonFile(selectedPath);
            view.replaceTasks(tasks);
            view.showSuccessMessage("Imported " + tasks.size() + " tasks from " + selectedPath + ".");
        } catch (IOException exception) {
            view.showErrorMessage("Failed to read task set file: " + exception.getMessage());
        } catch (RuntimeException exception) {
            view.showErrorMessage("Invalid task set JSON: " + exception.getMessage());
        }
    }

    private void handleRunScheduleButtonClick() {
        long startedAtMillis = System.currentTimeMillis();
        List<Task> tasks;
        try {
            tasks = writeTasksToJsonFile();
        } catch (IOException exception) {
            writeBackendRunLog(startedAtMillis, safeTaskCount(), false, false, rootMessage(exception), "");
            view.showErrorMessage("Failed to prepare task_set.json: " + exception.getMessage());
            return;
        } catch (RuntimeException exception) {
            writeBackendRunLog(startedAtMillis, safeTaskCount(), false, false, rootMessage(exception), "");
            view.showErrorMessage("Failed to prepare task_set.json: " + exception.getMessage());
            return;
        }

        view.setBusy(true);
        SwingWorker<BackendService.ScheduleRunResult, Void> worker =
                new SwingWorker<>() {
                    @Override
                    protected BackendService.ScheduleRunResult doInBackground() throws Exception {
                        return backendService.runSchedule();
                    }

                    @Override
                    protected void done() {
                        view.setBusy(false);
                        try {
                            BackendService.ScheduleRunResult result = get();
                            writeBackendRunLog(
                                    startedAtMillis,
                                    tasks.size(),
                                    true,
                                    true,
                                    "Schedule completed successfully.",
                                    result.output()
                            );
                            view.showSuccessMessage(
                                    "Schedule completed successfully.\n\n"
                                            + summarizeOutput(result.output())
                            );
                            backendService.openOutputWindow();
                        } catch (Exception exception) {
                            String message = rootMessage(exception);
                            writeBackendRunLog(startedAtMillis, tasks.size(), true, false, message, "");
                            view.showErrorMessage("Schedule failed.\n\n" + message);
                        }
                    }
                };
        worker.execute();
    }

    private void exportTasksToJsonFile(boolean showSuccessMessage) {
        try {
            writeTasksToJsonFile();
            if (showSuccessMessage) {
                view.showSuccessMessage("task_set.json exported to output folder successfully.");
            }
        } catch (IOException exception) {
            if (showSuccessMessage) {
                view.showErrorMessage("Failed to export task_set.json.");
            }
            throw new IllegalStateException(exception);
        } catch (RuntimeException exception) {
            if (showSuccessMessage) {
                view.showErrorMessage("Invalid task data: " + exception.getMessage());
            }
            throw exception;
        }
    }

    private List<Task> writeTasksToJsonFile() throws IOException {
        List<Task> tasks = collectTasksFromView();
        taskSetValidator.validateTaskSet(tasks);
        String jsonContent = convertTasksToJson(tasks);
        saveJsonToFile(jsonContent);
        return tasks;
    }

    List<Task> collectTasksFromView() {
        List<Task> tasks = new ArrayList<>();
        int taskRowCount = view.getTaskRowCount();

        for (int rowIndex = 0; rowIndex < taskRowCount; rowIndex++) {
            Map<String, Integer> taskParameterRow = view.getTaskParameterRow(rowIndex);
            tasks.add(createTaskFromRow(taskParameterRow, rowIndex + 1));
        }

        return tasks;
    }

    String convertTasksToJson(List<Task> tasks) {
        return "{\n"
                + "    \"periodic\": {"
                + buildPeriodicContent(tasks)
                + "\n"
                + "    }\n"
                + "}";
    }

    private void saveJsonToFile(String jsonContent) throws IOException {
        writeJsonFile(jsonContent);
    }

    private void writeJsonFile(String jsonContent) throws IOException {
        Path outputDirectory = Paths.get("output");
        Files.createDirectories(outputDirectory);
        Path outputPath = outputDirectory.resolve("task_set.json");
        Files.writeString(outputPath, jsonContent, StandardCharsets.UTF_8);
    }

    private List<Task> loadTasksFromJsonFile(Path path) throws IOException {
        String jsonContent = Files.readString(path, StandardCharsets.UTF_8);
        Object root = SimpleJsonParser.parse(jsonContent);
        if (!(root instanceof Map<?, ?> rootObject)) {
            throw new IllegalArgumentException("Root value must be a JSON object.");
        }

        List<Task> tasks;
        if (rootObject.containsKey("periodic")) {
            tasks = tasksFromPeriodicObject(rootObject.get("periodic"));
        } else if (rootObject.containsKey("tasks")) {
            tasks = tasksFromArray(rootObject.get("tasks"));
        } else {
            throw new IllegalArgumentException("Expected 'periodic' object or 'tasks' array.");
        }

        if (tasks.isEmpty()) {
            throw new IllegalArgumentException("Task set must contain at least one task.");
        }
        if (tasks.size() > 10) {
            throw new IllegalArgumentException("Maximum 10 tasks are allowed.");
        }

        taskSetValidator.validateTaskSet(tasks);
        return tasks;
    }

    private List<Task> tasksFromPeriodicObject(Object value) {
        if (!(value instanceof Map<?, ?> periodicObject)) {
            throw new IllegalArgumentException("'periodic' must be a JSON object.");
        }

        List<Map.Entry<?, ?>> entries = new ArrayList<>(periodicObject.entrySet());
        entries.sort(Comparator.comparingInt(this::taskEntryOrder)
                .thenComparing(entry -> String.valueOf(entry.getKey())));

        List<Task> tasks = new ArrayList<>();
        for (Map.Entry<?, ?> entry : entries) {
            if (!(entry.getValue() instanceof Map<?, ?> taskObject)) {
                throw new IllegalArgumentException("Task '" + entry.getKey() + "' must be an object.");
            }
            tasks.add(createTaskFromJsonObject(taskObject));
        }
        return tasks;
    }

    private int taskEntryOrder(Map.Entry<?, ?> entry) {
        String key = String.valueOf(entry.getKey());
        int index = key.length() - 1;
        while (index >= 0 && Character.isDigit(key.charAt(index))) {
            index--;
        }
        if (index == key.length() - 1) {
            return Integer.MAX_VALUE;
        }
        return Integer.parseInt(key.substring(index + 1));
    }

    private List<Task> tasksFromArray(Object value) {
        if (!(value instanceof List<?> taskArray)) {
            throw new IllegalArgumentException("'tasks' must be a JSON array.");
        }

        List<Task> tasks = new ArrayList<>();
        for (Object item : taskArray) {
            if (!(item instanceof Map<?, ?> taskObject)) {
                throw new IllegalArgumentException("Every item in 'tasks' must be an object.");
            }
            tasks.add(createTaskFromJsonObject(taskObject));
        }
        return tasks;
    }

    private Task createTaskFromJsonObject(Map<?, ?> taskObject) {
        return new Task(
                getRequiredInt(taskObject, "r", "release_time"),
                getRequiredInt(taskObject, "p", "period"),
                getRequiredInt(taskObject, "e", "execution_time"),
                getRequiredInt(taskObject, "d", "deadline", "relative_deadline"),
                getRequiredInt(taskObject, "w", "energy"),
                getOptionalInt(taskObject, 1, "preempt", "preemptive")
        );
    }

    private int getRequiredInt(Map<?, ?> object, String... keys) {
        Object value = findFirstValue(object, keys);
        if (value == null) {
            throw new IllegalArgumentException("Missing task parameter: " + String.join("/", keys));
        }
        return asInt(value, String.join("/", keys));
    }

    private int getOptionalInt(Map<?, ?> object, int defaultValue, String... keys) {
        Object value = findFirstValue(object, keys);
        if (value == null) {
            return defaultValue;
        }
        return asInt(value, String.join("/", keys));
    }

    private Object findFirstValue(Map<?, ?> object, String... keys) {
        for (String key : keys) {
            if (object.containsKey(key)) {
                return object.get(key);
            }
        }
        return null;
    }

    private int asInt(Object value, String parameterName) {
        if (value instanceof Number numberValue) {
            double doubleValue = numberValue.doubleValue();
            int intValue = numberValue.intValue();
            if (Math.abs(doubleValue - intValue) < 0.000001) {
                return intValue;
            }
        }
        throw new IllegalArgumentException(parameterName + " must be an integer.");
    }

    private boolean isValidRowIndex(int rowIndex) {
        return rowIndex >= 0 && rowIndex < view.getTaskRowCount();
    }

    private String buildPeriodicContent(List<Task> tasks) {
        List<String> taskEntries = new ArrayList<>();

        for (int taskIndex = 0; taskIndex < tasks.size(); taskIndex++) {
            int taskNumber = taskIndex + 1;
            boolean isLastTask = taskIndex == tasks.size() - 1;
            taskEntries.add(buildTaskEntry(taskNumber, tasks.get(taskIndex), isLastTask));
        }

        return String.join("", taskEntries);
    }

    private String buildTaskEntry(int taskNumber, Task task, boolean isLastTask) {
        String lineEnding = isLastTask ? "" : ",";
        return "\n"
                + "        \"p" + taskNumber + "\": "
                + buildTaskJson(task)
                + lineEnding;
    }

    private String buildTaskJson(Task task) {
        return "{\"r\": " + task.getR()
                + ", \"p\": " + task.getP()
                + ", \"e\": " + task.getE()
                + ", \"d\": " + task.getD()
                + ", \"w\": " + task.getW()
                + ", \"preempt\": " + task.getPreempt()
                + "}";
    }

    private Task createTaskFromRow(Map<String, Integer> taskParameterRow, int rowNumber) {
        Task task = new Task(
                getRequiredParameter(taskParameterRow, "r"),
                getRequiredParameter(taskParameterRow, "p"),
                getRequiredParameter(taskParameterRow, "e"),
                getRequiredParameter(taskParameterRow, "d"),
                getRequiredParameter(taskParameterRow, "w"),
                getRequiredParameter(taskParameterRow, "preempt")
        );
        taskSetValidator.validateTask(task, rowNumber);
        return task;
    }

    private int getRequiredParameter(
            Map<String, Integer> taskParameterRow,
            String parameterName
    ) {
        Integer parameterValue = taskParameterRow.get(parameterName);

        if (parameterValue == null) {
            throw new IllegalArgumentException("Missing task parameter: " + parameterName);
        }

        return parameterValue;
    }

    private String summarizeOutput(String output) {
        if (output == null || output.isBlank()) {
            return "No console output.";
        }
        int maximumLength = 1200;
        if (output.length() <= maximumLength) {
            return output;
        }
        return output.substring(0, maximumLength) + "\n...";
    }

    private int safeTaskCount() {
        try {
            return collectTasksFromView().size();
        } catch (RuntimeException exception) {
            return 0;
        }
    }

    private void writeBackendRunLog(
            long startedAtMillis,
            int taskCount,
            boolean validationPassed,
            boolean pythonSucceeded,
            String message,
            String pythonOutput
    ) {
        try {
            backendLogService.appendRunLog(backendLogService.createRunLog(
                    startedAtMillis,
                    taskCount,
                    validationPassed,
                    pythonSucceeded,
                    message,
                    pythonOutput
            ));
        } catch (IOException exception) {
            System.err.println("Failed to write Java backend log: " + exception.getMessage());
        }
    }

    private String rootMessage(Throwable exception) {
        Throwable current = exception;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current.getMessage() == null ? current.toString() : current.getMessage();
    }
}
