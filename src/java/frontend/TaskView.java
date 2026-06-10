import javax.swing.*;
import java.util.Map;

public class TaskView extends JFrame implements TaskInputView {

    private JTable taskTable;
    private JButton addButton;
    private JButton deleteButton;
    private JButton exportButton;

    private Runnable onAddCallback;
    private Runnable onDeleteCallback;
    private Runnable onExportCallback;

    public TaskView() {
    }

    @Override
    public int getTaskRowCount() {
        return 0;
    }

    @Override
    public Map<String, Integer> getTaskParameterRow(int rowIndex) {
        return null;
    }

    @Override
    public int getSelectedRowIndex() {
        return -1;
    }

    @Override
    public void addEmptyRow() {
    }

    @Override
    public void deleteRow(int rowIndex) {
    }

    @Override
    public void onAddButtonClicked(Runnable callback) {
        this.onAddCallback = callback;
    }

    @Override
    public void onDeleteButtonClicked(Runnable callback) {
        this.onDeleteCallback = callback;
    }

    @Override
    public void onExportButtonClicked(Runnable callback) {
        this.onExportCallback = callback;
    }

    @Override
    public void showSuccessMessage(String message) {
    }

    @Override
    public void showErrorMessage(String message) {
    }
}
