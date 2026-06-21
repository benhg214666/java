import java.util.List;

public record TaskSchedule(
        String taskId,
        double waitingTime,
        double turnaroundTime,
        List<ExecutionSegment> segments
) {

    public TaskSchedule {
        segments = List.copyOf(segments);
    }
}
