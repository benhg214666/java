import java.util.List;

public class TaskController {

    private TaskInputView taskInputView;

    public TaskController(TaskInputView taskInputView) {
        this.taskInputView = taskInputView;
        registerEventListeners();
    }

    private void registerEventListeners() {
    }

    private void handleAddButtonClick() {
    }

    private void handleDeleteButtonClick() {
    }

    private void handleExportButtonClick() {
    }

    List<Task> collectTasksFromView() {
        return null;
    }

    String convertTasksToJson(List<Task> tasks) {
        return null;
    }
}
