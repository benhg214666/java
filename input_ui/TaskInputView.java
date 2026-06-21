import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public interface TaskInputView {

    int getTaskRowCount();

    Map<String, Integer> getTaskParameterRow(int rowIndex);

    int getSelectedRowIndex();

    void addEmptyRow();

    void deleteRow(int rowIndex);

    void replaceTasks(List<Task> tasks);

    Path chooseTaskSetJsonFile();

    void onAddButtonClicked(Runnable callback);

    void onDeleteButtonClicked(Runnable callback);

    void onImportButtonClicked(Runnable callback);

    void onExportButtonClicked(Runnable callback);

    void onRunScheduleButtonClicked(Runnable callback);

    void setBusy(boolean busy);

    void showSuccessMessage(String message);

    void showErrorMessage(String message);
}
