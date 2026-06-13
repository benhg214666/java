import javax.swing.JPanel;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class GanttChartPanel extends JPanel {

    private static final Color JOB_COLOR = new Color(52, 120, 246);
    private static final Color GRID_COLOR = new Color(220, 226, 235);
    private static final Color TEXT_COLOR = new Color(32, 38, 46);
    private static final int LEFT_MARGIN = 160;
    private static final int RIGHT_MARGIN = 32;
    private static final int TOP_MARGIN = 44;
    private static final int ROW_HEIGHT = 30;
    private static final int BAR_HEIGHT = 16;

    private ScheduleData scheduleData;

    public GanttChartPanel() {
        setBackground(Color.WHITE);
        setPreferredSize(new Dimension(900, 360));
    }

    public void setScheduleData(ScheduleData scheduleData) {
        this.scheduleData = scheduleData;
        revalidate();
        repaint();
    }

    @Override
    protected void paintComponent(Graphics graphics) {
        super.paintComponent(graphics);
        Graphics2D graphics2D = (Graphics2D) graphics.create();
        graphics2D.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        try {
            if (scheduleData == null || scheduleData.frames().isEmpty()) {
                drawEmptyState(graphics2D);
                return;
            }
            drawChart(graphics2D);
        } finally {
            graphics2D.dispose();
        }
    }

    private void drawEmptyState(Graphics2D graphics2D) {
        graphics2D.setColor(TEXT_COLOR);
        graphics2D.drawString("No schedule data loaded.", LEFT_MARGIN, TOP_MARGIN);
    }

    private void drawChart(Graphics2D graphics2D) {
        List<Row> rows = buildRows();
        int maxTime = Math.max(1, scheduleData.frames().stream()
                .mapToInt(FrameEntry::t)
                .max()
                .orElse(1) + 1);

        int chartWidth = Math.max(1, getWidth() - LEFT_MARGIN - RIGHT_MARGIN);
        drawGrid(graphics2D, maxTime, chartWidth, rows.size());

        FontMetrics metrics = graphics2D.getFontMetrics();
        for (int index = 0; index < rows.size(); index++) {
            Row row = rows.get(index);
            int rowTop = TOP_MARGIN + index * ROW_HEIGHT;
            int barY = rowTop + (ROW_HEIGHT - BAR_HEIGHT) / 2;

            graphics2D.setColor(TEXT_COLOR);
            graphics2D.drawString(row.label(), 12, rowTop + (ROW_HEIGHT + metrics.getAscent()) / 2 - 3);
            graphics2D.setColor(JOB_COLOR);
            for (ExecutionSegment segment : row.segments()) {
                int x = LEFT_MARGIN + scale(segment.start(), maxTime, chartWidth);
                int width = Math.max(2, scale(segment.end(), maxTime, chartWidth) - scale(segment.start(), maxTime, chartWidth));
                graphics2D.fillRoundRect(x, barY, width, BAR_HEIGHT, 6, 6);
            }
        }

        setPreferredSize(new Dimension(900, TOP_MARGIN + rows.size() * ROW_HEIGHT + 36));
    }

    private void drawGrid(Graphics2D graphics2D, int maxTime, int chartWidth, int rowCount) {
        graphics2D.setColor(GRID_COLOR);
        graphics2D.setStroke(new BasicStroke(1f));
        int gridLines = Math.min(12, maxTime);
        for (int index = 0; index <= gridLines; index++) {
            int time = (int) Math.round(index * (maxTime / (double) gridLines));
            int x = LEFT_MARGIN + scale(time, maxTime, chartWidth);
            graphics2D.drawLine(x, TOP_MARGIN - 8, x, TOP_MARGIN + rowCount * ROW_HEIGHT);
            graphics2D.setColor(TEXT_COLOR);
            graphics2D.drawString(String.valueOf(time), x - 6, TOP_MARGIN - 14);
            graphics2D.setColor(GRID_COLOR);
        }
    }

    private int scale(int value, int maxTime, int chartWidth) {
        return (int) Math.round(value * (chartWidth / (double) maxTime));
    }

    private List<Row> buildRows() {
        Set<String> tasks = new LinkedHashSet<>();
        for (FrameEntry frame : scheduleData.frames()) {
            tasks.addAll(frame.runningJobs());
        }

        List<Row> rows = new ArrayList<>();
        for (String taskId : tasks) {
            List<ExecutionSegment> segments = new ArrayList<>();
            for (FrameEntry frame : scheduleData.frames()) {
                if (frame.runningJobs().contains(taskId)) {
                    segments.add(new ExecutionSegment(frame.t(), frame.t() + 1));
                }
            }
            rows.add(new Row(taskId, segments));
        }
        return rows;
    }

    private record Row(String label, List<ExecutionSegment> segments) {
    }
}
