import java.util.List;
import java.util.Map;

public record FrameEntry(
        int t,
        int frameId,
        List<String> runningJobs,
        double sell,
        Map<String, Number> power,
        Map<String, Number> soc
) {
}
