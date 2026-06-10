import java.util.Map;

public interface TaskInputView {

    int getTaskRowCount();

    Map<String, Integer> getTaskParameterRow(int rowIndex);

    int getSelectedRowIndex();

    void addEmptyRow();

    void deleteRow(int rowIndex);

    void onAddButtonClicked(Runnable callback);

    void onDeleteButtonClicked(Runnable callback);

    void onExportButtonClicked(Runnable callback);

    void showSuccessMessage(String message);

    void showErrorMessage(String message);
}
