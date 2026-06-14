import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class TaskController {

    private TaskInputView view;

    public TaskController(TaskInputView view) {
        this.view = view;
        registerEventListeners();
    }

    private void registerEventListeners() {
        view.onAddButtonClicked(this::handleAddButtonClick);
        view.onDeleteButtonClicked(this::handleDeleteButtonClick);
        view.onExportButtonClicked(this::handleExportButtonClick);
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
        exportTasksToJsonFile();
    }

    private void exportTasksToJsonFile() {
        try {
            List<Task> tasks = collectTasksFromView();
            String jsonContent = convertTasksToJson(tasks);
            saveJsonToFile(jsonContent);
            view.showSuccessMessage("task_set.json exported to output folder successfully.");
        } catch (IOException exception) {
            view.showErrorMessage("Failed to export task_set.json.");
        }
    }

    List<Task> collectTasksFromView() {
        List<Task> tasks = new ArrayList<>();
        int taskRowCount = view.getTaskRowCount();

        for (int rowIndex = 0; rowIndex < taskRowCount; rowIndex++) {
            Map<String, Integer> taskParameterRow = view.getTaskParameterRow(rowIndex);
            tasks.add(createTaskFromRow(taskParameterRow));
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

    private Task createTaskFromRow(Map<String, Integer> taskParameterRow) {
        return new Task(
                getRequiredParameter(taskParameterRow, "r"),
                getRequiredParameter(taskParameterRow, "p"),
                getRequiredParameter(taskParameterRow, "e"),
                getRequiredParameter(taskParameterRow, "d"),
                getRequiredParameter(taskParameterRow, "w"),
                getRequiredParameter(taskParameterRow, "preempt")
        );
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
}
