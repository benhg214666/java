import java.util.List;

public record AlgorithmSchedule(
        String name,
        ScheduleMetrics metrics,
        List<TaskSchedule> tasks
) {

    public AlgorithmSchedule {
        tasks = List.copyOf(tasks);
    }
}
