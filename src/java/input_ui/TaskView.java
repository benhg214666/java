import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.util.LinkedHashMap;
import java.util.Map;

public class TaskView extends JFrame implements TaskInputView {

    private static final String[] COLUMN_NAMES = {
            "release time",
            "period",
            "execution time",
            "deadline",
            "energy demand",
            "preempt"
    };

    private static final Object[] DEFAULT_ROW_VALUES = {0, 0, 0, 0, 0, 1};
    private static final int MAX_TASK_COUNT = 10;

    private JTable taskTable;
    private DefaultTableModel tableModel;
    private JButton addButton;
    private JButton deleteButton;
    private JButton exportButton;

    public TaskView() {
        initializeFrame();
        initializeTable();
        initializeButtons();
        layoutComponents();
    }

    @Override
    public int getTaskRowCount() {
        return tableModel.getRowCount();
    }

    @Override
    public Map<String, Integer> getTaskParameterRow(int rowIndex) {
        Map<String, Integer> taskParameters = new LinkedHashMap<>();
        taskParameters.put("r", getIntegerValue(rowIndex, 0));
        taskParameters.put("p", getIntegerValue(rowIndex, 1));
        taskParameters.put("e", getIntegerValue(rowIndex, 2));
        taskParameters.put("d", getIntegerValue(rowIndex, 3));
        taskParameters.put("w", getIntegerValue(rowIndex, 4));
        taskParameters.put("preempt", getIntegerValue(rowIndex, 5));
        return taskParameters;
    }

    @Override
    public int getSelectedRowIndex() {
        return taskTable.getSelectedRow();
    }

    @Override
    public void addEmptyRow() {
        if (hasReachedMaximumTaskCount()) {
            showErrorMessage("Maximum 10 tasks are allowed.");
            return;
        }

        tableModel.addRow(createDefaultTaskRow());
    }

    @Override
    public void deleteRow(int rowIndex) {
        if (isValidRowIndex(rowIndex)) {
            tableModel.removeRow(rowIndex);
        }
    }

    @Override
    public void onAddButtonClicked(Runnable callback) {
        addButton.addActionListener(event -> callback.run());
    }

    @Override
    public void onDeleteButtonClicked(Runnable callback) {
        deleteButton.addActionListener(event -> callback.run());
    }

    @Override
    public void onExportButtonClicked(Runnable callback) {
        exportButton.addActionListener(event -> callback.run());
    }

    @Override
    public void showSuccessMessage(String message) {
        JOptionPane.showMessageDialog(this, message, "Success", JOptionPane.INFORMATION_MESSAGE);
    }

    @Override
    public void showErrorMessage(String message) {
        JOptionPane.showMessageDialog(this, message, "Error", JOptionPane.ERROR_MESSAGE);
    }

    private void initializeFrame() {
        setTitle("VPP Task Input");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setSize(800, 400);
        setLocationRelativeTo(null);
    }

    private void initializeTable() {
        tableModel = new DefaultTableModel(COLUMN_NAMES, 0);
        taskTable = new JTable(tableModel);
        addEmptyRow();
    }

    private void initializeButtons() {
        addButton = new JButton("Add Row");
        deleteButton = new JButton("Delete Row");
        exportButton = new JButton("Export JSON");
    }

    private void layoutComponents() {
        add(new JScrollPane(taskTable), BorderLayout.CENTER);
        add(createButtonPanel(), BorderLayout.SOUTH);
    }

    private JPanel createButtonPanel() {
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        buttonPanel.add(addButton);
        buttonPanel.add(deleteButton);
        buttonPanel.add(exportButton);
        return buttonPanel;
    }

    private int getIntegerValue(int rowIndex, int columnIndex) {
        Object cellValue = tableModel.getValueAt(rowIndex, columnIndex);
        return parseIntegerValue(cellValue);
    }

    private int parseIntegerValue(Object cellValue) {
        if (cellValue instanceof Number numberValue) {
            return numberValue.intValue();
        }
        return Integer.parseInt(String.valueOf(cellValue).trim());
    }

    private boolean isValidRowIndex(int rowIndex) {
        return rowIndex >= 0 && rowIndex < tableModel.getRowCount();
    }

    private boolean hasReachedMaximumTaskCount() {
        return tableModel.getRowCount() >= MAX_TASK_COUNT;
    }

    private Object[] createDefaultTaskRow() {
        return DEFAULT_ROW_VALUES.clone();
    }
}
