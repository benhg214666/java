import java.util.List;

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
        return null;
    }

    String convertTasksToJson(List<Task> tasks) {
        return null;
    }

    private boolean isValidRowIndex(int rowIndex) {
        return rowIndex >= 0 && rowIndex < view.getTaskRowCount();
    }
}
