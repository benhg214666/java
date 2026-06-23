import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class TaskSetValidator {

    private static final int HORIZON = 72;
    private static final int FRAME_SIZE = 4;
    private static final int MIN_TASK_COUNT = 6;
    private static final int MAX_TASK_COUNT = 10;
    private static final double MIN_WORKLOAD_DENSITY = 0.7;
    private static final double MAX_WORKLOAD_DENSITY = 0.9;

    public void validateTask(Task task, int rowNumber) {
        List<String> errors = new ArrayList<>();
        addTaskErrors(task, rowNumber, errors);
        throwIfInvalid(errors);
    }

    public void validateTaskSet(List<Task> tasks) {
        List<String> errors = new ArrayList<>();

        if (tasks.size() < MIN_TASK_COUNT || tasks.size() > MAX_TASK_COUNT) {
            errors.add("Task count must be between 6 and 10.");
        }

        for (int index = 0; index < tasks.size(); index++) {
            addTaskErrors(tasks.get(index), index + 1, errors);
        }

        validatePeriodDiversity(tasks, errors);
        validateExpandedJobCount(tasks, errors);
        validateWorkloadDensity(tasks, errors);
        validateExecutionDistribution(tasks, errors);
        validateEnergyDistribution(tasks, errors);
        validateTightDeadlines(tasks, errors);
        validateNonPreemptiveTasks(tasks, errors);

        throwIfInvalid(errors);
    }

    private void addTaskErrors(Task task, int rowNumber, List<String> errors) {
        String prefix = "Row " + rowNumber + ": ";
        if (task.getR() < 1 || task.getR() > task.getP()) {
            errors.add(prefix + "release time must satisfy 1 <= r <= period.");
        }
        if (task.getP() < 6 || task.getP() > 24) {
            errors.add(prefix + "period must be between 6 and 24.");
        }
        if (task.getE() < 1 || task.getE() > 4) {
            errors.add(prefix + "execution time must be between 1 and 4.");
        }
        if (task.getD() < task.getE() || task.getD() > task.getP()) {
            errors.add(prefix + "deadline must satisfy execution time <= deadline <= period.");
        }
        if (task.getW() < 6 || task.getW() > 18) {
            errors.add(prefix + "energy demand must be between 6 and 18.");
        }
        if (task.getPreempt() != 0 && task.getPreempt() != 1) {
            errors.add(prefix + "preempt must be 0 or 1.");
        }
        if (task.getE() > FRAME_SIZE) {
            errors.add(prefix + "execution time cannot exceed frame size " + FRAME_SIZE + ".");
        }
        if (task.getP() >= 1 && frameBound(task.getP()) > task.getD()) {
            errors.add(prefix + "frame bound is larger than deadline.");
        }
        if (task.getP() >= 1 && task.getR() >= 1 && task.getD() >= task.getE()
                && lastReleaseExceedsHorizon(task)) {
            errors.add(prefix + "last released job exceeds the 72-hour horizon.");
        }
    }

    private void validatePeriodDiversity(List<Task> tasks, List<String> errors) {
        Set<Integer> periods = new HashSet<>();
        for (Task task : tasks) {
            periods.add(task.getP());
        }
        if (periods.size() < 3) {
            errors.add("Task set must contain at least 3 different periods.");
        }
    }

    private void validateExpandedJobCount(List<Task> tasks, List<String> errors) {
        int expandedJobs = 0;
        for (Task task : tasks) {
            if (task.getP() > 0 && task.getR() >= 1 && task.getR() <= HORIZON) {
                expandedJobs += ((HORIZON - task.getR()) / task.getP()) + 1;
            }
        }
        if (expandedJobs <= 30) {
            errors.add("Expanded periodic jobs inside the 72-hour horizon must be greater than 30.");
        }
    }

    private void validateWorkloadDensity(List<Task> tasks, List<String> errors) {
        double density = 0.0;
        for (Task task : tasks) {
            if (task.getP() > 0) {
                density += (double) task.getE() / task.getP();
            }
        }
        if (density < MIN_WORKLOAD_DENSITY || density > MAX_WORKLOAD_DENSITY) {
            errors.add(String.format(
                    "Workload density must be between %.1f and %.1f. Current: %.6f.",
                    MIN_WORKLOAD_DENSITY,
                    MAX_WORKLOAD_DENSITY,
                    density
            ));
        }
    }

    private void validateExecutionDistribution(List<Task> tasks, List<String> errors) {
        int executionTwoCount = 0;
        int executionAtLeastThreeCount = 0;
        for (Task task : tasks) {
            if (task.getE() == 2) {
                executionTwoCount++;
            }
            if (task.getE() >= 3) {
                executionAtLeastThreeCount++;
            }
        }
        if (executionTwoCount < 2) {
            errors.add("At least 2 tasks must have execution time = 2.");
        }
        if (executionAtLeastThreeCount < 1) {
            errors.add("At least 1 task must have execution time >= 3.");
        }
    }

    private void validateEnergyDistribution(List<Task> tasks, List<String> errors) {
        int highEnergyCount = 0;
        for (Task task : tasks) {
            if (task.getW() >= 14) {
                highEnergyCount++;
            }
        }
        if (highEnergyCount < 2) {
            errors.add("At least 2 tasks must have energy demand >= 14.");
        }
    }

    private void validateTightDeadlines(List<Task> tasks, List<String> errors) {
        int tightDeadlineCount = 0;
        for (Task task : tasks) {
            if (task.getD() == task.getE()) {
                tightDeadlineCount++;
            }
        }
        int requiredCount = (int) Math.ceil(tasks.size() * 0.2);
        if (tightDeadlineCount < requiredCount) {
            errors.add("At least 20% of tasks must have deadline = execution time.");
        }
    }

    private void validateNonPreemptiveTasks(List<Task> tasks, List<String> errors) {
        int nonPreemptiveCount = 0;
        for (Task task : tasks) {
            if (task.getE() != 1 && task.getPreempt() == 0) {
                nonPreemptiveCount++;
            }
        }
        if (nonPreemptiveCount < 2) {
            errors.add("At least 2 tasks with execution time != 1 must be non-preemptive.");
        }
    }

    private boolean lastReleaseExceedsHorizon(Task task) {
        int lastRelease = task.getR() + ((HORIZON - task.getR()) / task.getP()) * task.getP();
        return lastRelease + task.getD() - 1 > HORIZON;
    }

    private int frameBound(int period) {
        return 2 * FRAME_SIZE - gcd(FRAME_SIZE, period);
    }

    private int gcd(int a, int b) {
        int left = Math.abs(a);
        int right = Math.abs(b);
        while (right != 0) {
            int next = left % right;
            left = right;
            right = next;
        }
        return left;
    }

    private void throwIfInvalid(List<String> errors) {
        if (!errors.isEmpty()) {
            throw new IllegalArgumentException(String.join(System.lineSeparator(), errors));
        }
    }
}
