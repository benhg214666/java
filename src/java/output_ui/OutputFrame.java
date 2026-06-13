import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTable;
import javax.swing.SwingUtilities;
import javax.swing.table.DefaultTableModel;
import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;

public class OutputFrame extends JFrame {

    private static final DateTimeFormatter UPDATE_TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JsonImportService jsonImportService;
    private final JLabel statusLabel;
    private final DefaultTableModel tableModel;
    private final GanttChartPanel ganttChartPanel;

    public OutputFrame() {
        this(new JsonImportService());
    }

    OutputFrame(JsonImportService jsonImportService) {
        this.jsonImportService = jsonImportService;
        this.statusLabel = new JLabel("尚未載入");
        this.tableModel = createTableModel();
        this.ganttChartPanel = new GanttChartPanel();
        initializeFrame();
        layoutComponents();
        refreshScheduleData();
    }

    private void initializeFrame() {
        setTitle("Schedule Result Viewer");
        setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE);
        setSize(1100, 720);
        setLocationRelativeTo(null);
    }

    private void layoutComponents() {
        JPanel rootPanel = new JPanel(new BorderLayout(12, 12));
        rootPanel.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12));
        rootPanel.add(createControlPanel(), BorderLayout.NORTH);
        rootPanel.add(createContentPanel(), BorderLayout.CENTER);
        setContentPane(rootPanel);
    }

    private JPanel createControlPanel() {
        JButton refreshButton = new JButton("重新整理 (Refresh)");
        refreshButton.addActionListener(event -> refreshScheduleData());

        JPanel controlPanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 12, 0));
        controlPanel.add(refreshButton);
        controlPanel.add(statusLabel);
        return controlPanel;
    }

    private JPanel createContentPanel() {
        JTable scheduleTable = new JTable(tableModel);
        scheduleTable.setRowHeight(26);

        JScrollPane tableScrollPane = new JScrollPane(scheduleTable);
        tableScrollPane.setBorder(BorderFactory.createTitledBorder("Schedule Result"));

        JScrollPane ganttScrollPane = new JScrollPane(ganttChartPanel);
        ganttScrollPane.setBorder(BorderFactory.createTitledBorder("執行工作甘特圖"));

        JPanel contentPanel = new JPanel(new BorderLayout(0, 12));
        contentPanel.add(tableScrollPane, BorderLayout.NORTH);
        contentPanel.add(ganttScrollPane, BorderLayout.CENTER);
        return contentPanel;
    }

    private DefaultTableModel createTableModel() {
        return new DefaultTableModel(
                new Object[]{"時間", "Frame", "執行工作", "Sell", "P", "SOC"},
                0
        ) {
            @Override
            public boolean isCellEditable(int row, int column) {
                return false;
            }
        };
    }

    private void refreshScheduleData() {
        try {
            ScheduleData scheduleData = jsonImportService.loadScheduleData();
            updateScheduleTable(scheduleData);
            ganttChartPanel.setScheduleData(scheduleData);
            statusLabel.setText("最後更新：" + LocalDateTime.now().format(UPDATE_TIME_FORMATTER));
        } catch (ScheduleDataLoadException exception) {
            statusLabel.setText("載入失敗");
            JOptionPane.showMessageDialog(
                    this,
                    exception.getMessage(),
                    "Schedule Data Load Error",
                    JOptionPane.ERROR_MESSAGE
            );
        }
    }

    private void updateScheduleTable(ScheduleData scheduleData) {
        tableModel.setRowCount(0);
        for (FrameEntry frame : scheduleData.frames()) {
            tableModel.addRow(new Object[]{
                    frame.t(),
                    frame.frameId(),
                    String.join(", ", frame.runningJobs()),
                    format(frame.sell()),
                    formatMap(frame.power()),
                    formatMap(frame.soc())
            });
        }
    }

    private String format(double value) {
        return String.format("%.2f", value);
    }

    private String formatMap(Map<String, Number> values) {
        if (values.isEmpty()) {
            return "-";
        }
        StringBuilder builder = new StringBuilder();
        boolean first = true;
        for (Map.Entry<String, Number> entry : values.entrySet()) {
            if (!first) {
                builder.append(", ");
            }
            first = false;
            builder.append(entry.getKey()).append(": ").append(format(entry.getValue().doubleValue()));
        }
        return builder.toString();
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new OutputFrame().setVisible(true));
    }
}
