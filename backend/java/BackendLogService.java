import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

public class BackendLogService {

    private static final DateTimeFormatter TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final String LOG_FILE = "java_backend_log.json";

    private final Path projectRoot;

    public BackendLogService(Path projectRoot) {
        this.projectRoot = projectRoot;
    }

    public void appendRunLog(BackendRunLog log) throws IOException {
        Path outputDirectory = projectRoot.resolve("output");
        Files.createDirectories(outputDirectory);
        Path logPath = outputDirectory.resolve(LOG_FILE);
        String entryJson = toJson(log);

        if (!Files.exists(logPath)) {
            Files.writeString(
                    logPath,
                    "{\n"
                            + "  \"runs\": [\n"
                            + indent(entryJson, 4)
                            + "\n"
                            + "  ]\n"
                            + "}\n",
                    StandardCharsets.UTF_8
            );
            return;
        }

        String existingContent = Files.readString(logPath, StandardCharsets.UTF_8).trim();
        int arrayEndIndex = existingContent.lastIndexOf(']');
        if (arrayEndIndex < 0) {
            throw new IOException("Invalid backend log file format: " + logPath);
        }

        String beforeArrayEnd = existingContent.substring(0, arrayEndIndex).trim();
        boolean hasExistingRuns = beforeArrayEnd.endsWith("}");
        StringBuilder updatedContent = new StringBuilder();
        updatedContent.append(existingContent, 0, arrayEndIndex);
        if (hasExistingRuns) {
            updatedContent.append(",");
        }
        updatedContent.append(System.lineSeparator());
        updatedContent.append(indent(entryJson, 4));
        updatedContent.append(System.lineSeparator());
        updatedContent.append(existingContent.substring(arrayEndIndex));
        updatedContent.append(System.lineSeparator());
        Files.writeString(logPath, updatedContent.toString(), StandardCharsets.UTF_8);
    }

    public BackendRunLog createRunLog(
            long startedAtMillis,
            int taskCount,
            boolean validationPassed,
            boolean pythonSucceeded,
            String message,
            String pythonOutput
    ) {
        return new BackendRunLog(
                LocalDateTime.now().format(TIME_FORMATTER),
                taskCount,
                validationPassed,
                pythonSucceeded,
                System.currentTimeMillis() - startedAtMillis,
                outputFileStatus(),
                message,
                preview(pythonOutput)
        );
    }

    private Map<String, Boolean> outputFileStatus() {
        Map<String, Boolean> status = new LinkedHashMap<>();
        status.put("task_set", Files.exists(projectRoot.resolve("output/task_set.json")));
        status.put("schedule_result", Files.exists(projectRoot.resolve("output/schedule_result.json")));
        status.put("acceptance_test_log", Files.exists(projectRoot.resolve("output/acceptance_test_log.json")));
        status.put("evaluation_results", Files.exists(projectRoot.resolve("output/evaluation_results.json")));
        return status;
    }

    private String toJson(BackendRunLog log) {
        return "{\n"
                + "  \"timestamp\": \"" + escape(log.timestamp()) + "\",\n"
                + "  \"task_count\": " + log.taskCount() + ",\n"
                + "  \"validation_passed\": " + log.validationPassed() + ",\n"
                + "  \"python_succeeded\": " + log.pythonSucceeded() + ",\n"
                + "  \"duration_ms\": " + log.durationMillis() + ",\n"
                + "  \"output_files\": " + outputFilesJson(log.outputFiles()) + ",\n"
                + "  \"message\": \"" + escape(log.message()) + "\",\n"
                + "  \"python_output_preview\": \"" + escape(log.pythonOutputPreview()) + "\"\n"
                + "}";
    }

    private String outputFilesJson(Map<String, Boolean> outputFiles) {
        StringBuilder builder = new StringBuilder();
        builder.append("{");
        boolean first = true;
        for (Map.Entry<String, Boolean> entry : outputFiles.entrySet()) {
            if (!first) {
                builder.append(", ");
            }
            first = false;
            builder.append("\"")
                    .append(escape(entry.getKey()))
                    .append("\": ")
                    .append(entry.getValue());
        }
        builder.append("}");
        return builder.toString();
    }

    private String preview(String text) {
        if (text == null || text.isBlank()) {
            return "";
        }
        int maximumLength = 800;
        return text.length() <= maximumLength ? text : text.substring(0, maximumLength) + "...";
    }

    private String indent(String text, int spaces) {
        String prefix = " ".repeat(spaces);
        return prefix + text.replace("\n", "\n" + prefix);
    }

    private String escape(String value) {
        if (value == null) {
            return "";
        }
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\r", "\\r")
                .replace("\n", "\\n")
                .replace("\t", "\\t");
    }

    public record BackendRunLog(
            String timestamp,
            int taskCount,
            boolean validationPassed,
            boolean pythonSucceeded,
            long durationMillis,
            Map<String, Boolean> outputFiles,
            String message,
            String pythonOutputPreview
    ) {
    }
}
