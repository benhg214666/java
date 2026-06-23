import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class EvaluationResultParser {

    private final Path projectRoot;

    public EvaluationResultParser(Path projectRoot) {
        this.projectRoot = projectRoot;
    }

    public EvaluationSummary loadSummary() throws IOException {
        Path evaluationPath = projectRoot.resolve("output/evaluation_results.json");
        if (!Files.exists(evaluationPath)) {
            throw new IOException("Evaluation result file not found: " + evaluationPath);
        }

        Object parsedJson = SimpleJsonParser.parse(Files.readString(evaluationPath));
        Map<String, Object> root = requireObject(parsedJson, "evaluation root");
        return new EvaluationSummary(
                numberValue(root, "hard_deadline_miss_rate"),
                numberValue(root, "soft_deadline_miss_rate"),
                numberValue(root, "sporadic_value_rate"),
                numberValue(root, "generator_cost"),
                numberValue(root, "market_revenue"),
                numberValue(root, "objective_value"),
                intValue(root, "constraint_violation_count"),
                booleanValue(root, "verification_passed")
        );
    }

    private Map<String, Object> requireObject(Object value, String fieldName) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> converted = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!(entry.getKey() instanceof String key)) {
                    throw new IllegalArgumentException("Expected string key for " + fieldName);
                }
                converted.put(key, entry.getValue());
            }
            return converted;
        }
        throw new IllegalArgumentException("Expected object for " + fieldName);
    }

    private double numberValue(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        throw new IllegalArgumentException("Missing number: " + key);
    }

    private int intValue(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (value instanceof Number number) {
            return number.intValue();
        }
        throw new IllegalArgumentException("Missing integer: " + key);
    }

    private boolean booleanValue(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (value instanceof Boolean bool) {
            return bool;
        }
        throw new IllegalArgumentException("Missing boolean: " + key);
    }
}
