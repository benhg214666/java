import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import javax.swing.SwingWorker;

public class TaskController {

    private TaskInputView view;
    private final BackendService backendService;

    public TaskController(TaskInputView view) {
        this.view = view;
        this.backendService = new BackendService();
        registerEventListeners();
    }

    private void registerEventListeners() {
        view.onAddButtonClicked(this::handleAddButtonClick);
        view.onDeleteButtonClicked(this::handleDeleteButtonClick);
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

    private void handleRunScheduleButtonClick() {
        try {
            exportTasksToJsonFile(false);
        } catch (RuntimeException exception) {
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
                            view.showSuccessMessage(
                                    "Schedule completed successfully.\n\n"
                                            + summarizeOutput(result.output())
                            );
                            backendService.openOutputWindow();
                        } catch (Exception exception) {
                            view.showErrorMessage("Schedule failed.\n\n" + rootMessage(exception));
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

    private void writeTasksToJsonFile() throws IOException {
        List<Task> tasks = collectTasksFromView();
        String jsonContent = convertTasksToJson(tasks);
        saveJsonToFile(jsonContent);
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
        validateTask(task, rowNumber);
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

    private void validateTask(Task task, int rowNumber) {
        String prefix = "Row " + rowNumber + ": ";
        if (task.getR() < 1 || task.getR() > task.getP()) {
            throw new IllegalArgumentException(prefix + "release time must satisfy 1 <= r <= period.");
        }
        if (task.getP() < 6 || task.getP() > 24) {
            throw new IllegalArgumentException(prefix + "period must be between 6 and 24.");
        }
        if (task.getE() < 1 || task.getE() > 4) {
            throw new IllegalArgumentException(prefix + "execution time must be between 1 and 4.");
        }
        if (task.getD() < task.getE() || task.getD() > task.getP()) {
            throw new IllegalArgumentException(prefix + "deadline must satisfy execution time <= deadline <= period.");
        }
        if (task.getW() < 6 || task.getW() > 18) {
            throw new IllegalArgumentException(prefix + "energy demand must be between 6 and 18.");
        }
        if (task.getPreempt() != 0 && task.getPreempt() != 1) {
            throw new IllegalArgumentException(prefix + "preempt must be 0 or 1.");
        }
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

    private String rootMessage(Exception exception) {
        Throwable current = exception;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current.getMessage() == null ? current.toString() : current.getMessage();
    }
}
