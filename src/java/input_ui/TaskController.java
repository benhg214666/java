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
        view.showSuccessMessage("Export JSON will be implemented in the next phase.");
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
        return "{\"periodic\": {" + buildPeriodicContent(tasks) + "}}";
    }

    private boolean isValidRowIndex(int rowIndex) {
        return rowIndex >= 0 && rowIndex < view.getTaskRowCount();
    }

    private String buildPeriodicContent(List<Task> tasks) {
        List<String> taskEntries = new ArrayList<>();

        for (int taskIndex = 0; taskIndex < tasks.size(); taskIndex++) {
            int taskNumber = taskIndex + 1;
            taskEntries.add(buildTaskEntry(taskNumber, tasks.get(taskIndex)));
        }

        return String.join(", ", taskEntries);
    }

    private String buildTaskEntry(int taskNumber, Task task) {
        return "\"p" + taskNumber + "\": " + buildTaskJson(task);
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
