import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

public class BackendService {

    private static final String ADVANCED_SCHEDULER = "src/python/advanced_scheduler.py";
    private static final String BASIC_SCHEDULER = "src/python/scheduler.py";
    private static final String EVALUATOR = "src/python/evaluator.py";

    private final Path projectRoot;

    public BackendService() {
        this.projectRoot = findProjectRoot();
    }

    public ScheduleRunResult runSchedule() throws IOException, InterruptedException {
        ensureRequiredFilesExist();

        try {
            return runPythonScript(ADVANCED_SCHEDULER);
        } catch (IOException | RuntimeException exception) {
            return runBasicSchedulerAndEvaluator();
        }
    }

    public void openOutputWindow() {
        SwingUtilities.invokeLater(() -> {
            try {
                Class<?> outputFrameClass = Class.forName("OutputFrame");
                JFrame frame = (JFrame) outputFrameClass.getDeclaredConstructor().newInstance();
                frame.setVisible(true);
            } catch (ClassNotFoundException exception) {
                throw new IllegalStateException(
                        "OutputFrame not found. Compile and run with src/java/output_ui on the classpath.",
                        exception
                );
            } catch (
                    InstantiationException
                    | IllegalAccessException
                    | InvocationTargetException
                    | NoSuchMethodException exception
            ) {
                throw new IllegalStateException("Unable to open output window.", exception);
            }
        });
    }

    public Path getProjectRoot() {
        return projectRoot;
    }

    private ScheduleRunResult runBasicSchedulerAndEvaluator() throws IOException, InterruptedException {
        ScheduleRunResult schedulerResult = runPythonScript(BASIC_SCHEDULER);
        ScheduleRunResult evaluatorResult = runPythonScript(EVALUATOR);
        return schedulerResult.merge(evaluatorResult);
    }

    private ScheduleRunResult runPythonScript(String scriptPath) throws IOException, InterruptedException {
        List<String> errors = new ArrayList<>();
        for (List<String> command : pythonCommands(scriptPath)) {
            try {
                ProcessResult result = runCommand(command);
                if (result.exitCode() == 0) {
                    return new ScheduleRunResult(result.output());
                }
                errors.add(String.join(" ", command) + System.lineSeparator() + result.output());
            } catch (IOException exception) {
                errors.add(String.join(" ", command) + System.lineSeparator() + exception.getMessage());
            }
        }
        throw new IOException(
                "Python scheduling failed. Install Python or set PYTHON_EXE to python.exe."
                        + System.lineSeparator()
                        + String.join(System.lineSeparator(), errors)
        );
    }

    private ProcessResult runCommand(List<String> command) throws IOException, InterruptedException {
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(projectRoot.toFile());
        processBuilder.redirectErrorStream(true);

        Process process = processBuilder.start();
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8)
        )) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append(System.lineSeparator());
            }
        }

        return new ProcessResult(process.waitFor(), output.toString().trim());
    }

    private List<List<String>> pythonCommands(String scriptPath) {
        String root = projectRoot.toString();
        List<List<String>> commands = new ArrayList<>();
        String configuredPython = System.getenv("PYTHON_EXE");
        if (configuredPython != null && !configuredPython.isBlank()) {
            commands.add(List.of(configuredPython, scriptPath, "--base-dir", root));
        }
        commands.add(List.of("python", scriptPath, "--base-dir", root));
        commands.add(List.of("py", "-3", scriptPath, "--base-dir", root));
        commands.add(List.of("python3", scriptPath, "--base-dir", root));
        return commands;
    }

    private void ensureRequiredFilesExist() throws IOException {
        requireFile(projectRoot.resolve("output/task_set.json"));
        requireFile(projectRoot.resolve("input/processor_settings.json"));
        requireFile(projectRoot.resolve("input/price_72hr.json"));
    }

    private void requireFile(Path path) throws IOException {
        if (!Files.exists(path)) {
            throw new IOException("Required file not found: " + path);
        }
    }

    private Path findProjectRoot() {
        Path current = Path.of("").toAbsolutePath().normalize();
        while (current != null) {
            if (Files.isDirectory(current.resolve("src/python"))
                    && Files.isDirectory(current.resolve("input"))
                    && Files.isDirectory(current.resolve("output"))) {
                return current;
            }
            current = current.getParent();
        }
        return Path.of("").toAbsolutePath().normalize();
    }

    private record ProcessResult(int exitCode, String output) {
    }

    public record ScheduleRunResult(String output) {
        ScheduleRunResult merge(ScheduleRunResult other) {
            String separator = output.isBlank() || other.output.isBlank()
                    ? ""
                    : System.lineSeparator() + System.lineSeparator();
            return new ScheduleRunResult(output + separator + other.output);
        }
    }
}
