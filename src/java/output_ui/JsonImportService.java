import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

public class JsonImportService {

    private static final Logger LOGGER = Logger.getLogger(JsonImportService.class.getName());
    private static final String DEFAULT_RESULT_JSON_PATH = "output/schedule_result.json";
    private static final String LEGACY_RESULT_JSON_PATH = "output/result.json";

    public ScheduleData loadScheduleData() throws ScheduleDataLoadException {
        Path pathToLoad = resolveResultJsonPath();
        LOGGER.info("Loading schedule data from " + pathToLoad);
        if (!Files.exists(pathToLoad)) {
            ScheduleDataLoadException exception = new ScheduleDataLoadException(
                    "Schedule result file not found: " + pathToLoad
            );
            LOGGER.log(Level.SEVERE, "Schedule data file is missing: " + pathToLoad);
            throw exception;
        }

        try {
            String json = Files.readString(pathToLoad);
            ScheduleData scheduleData = toScheduleData(SimpleJsonParser.parse(json));
            LOGGER.info("Schedule data loaded successfully from " + pathToLoad);
            return scheduleData;
        } catch (IOException exception) {
            LOGGER.log(Level.SEVERE, "Unable to read schedule data from " + pathToLoad, exception);
            throw new ScheduleDataLoadException("Unable to read schedule result file: " + pathToLoad, exception);
        } catch (RuntimeException exception) {
            LOGGER.log(Level.SEVERE, "Invalid JSON schedule data in " + pathToLoad, exception);
            throw new ScheduleDataLoadException("Invalid JSON schedule data: " + pathToLoad, exception);
        }
    }

    private Path resolveResultJsonPath() {
        Path defaultPath = Path.of(DEFAULT_RESULT_JSON_PATH);
        if (Files.exists(defaultPath)) {
            return defaultPath;
        }
        Path legacyPath = Path.of(LEGACY_RESULT_JSON_PATH);
        if (Files.exists(legacyPath)) {
            LOGGER.info("Default schedule_result.json missing, falling back to " + legacyPath);
            return legacyPath;
        }
        return defaultPath;
    }

    @SuppressWarnings("unchecked")
    private ScheduleData toScheduleData(Object parsedJson) {
        Map<String, Object> root = requireObject(parsedJson, "root");
        List<Object> scheduleResultList = requireArray(
                findValue(root, "schedule_result", "scheduleResult"),
                "schedule_result"
        );

        List<FrameEntry> frames = new ArrayList<>();
        for (Object rawFrame : scheduleResultList) {
            Map<String, Object> frame = requireObject(rawFrame, "schedule_result item");
            int t = intValue(frame, "t", "time");
            int frameId = intValue(frame, "frame_id", "frameId");
            List<String> runningJobs = stringArray(requireArray(
                    findValue(frame, "running_jobs", "runningJobs"),
                    "running_jobs"
            ));
            double sell = numberValue(frame, "sell");
            Map<String, Number> power = toNumberMap(findValue(frame, "P", "power"));
            Map<String, Number> soc = toNumberMap(findValue(frame, "soc", "SoC", "state_of_charge"));
            frames.add(new FrameEntry(t, frameId, runningJobs, sell, power, soc));
        }

        return new ScheduleData(frames);
    }

    private List<String> stringArray(List<Object> values) {
        List<String> result = new ArrayList<>();
        for (Object value : values) {
            result.add(String.valueOf(value));
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Number> toNumberMap(Object rawObject) {
        if (rawObject == null) {
            return Map.of();
        }
        Map<String, Object> object = requireObject(rawObject, "number map");
        Map<String, Number> numbers = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : object.entrySet()) {
            Object value = entry.getValue();
            if (value instanceof Number number) {
                numbers.put(entry.getKey(), number);
            }
        }
        return numbers;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> requireObject(Object value, String fieldName) {
        if (value instanceof Map<?, ?> map) {
            return (Map<String, Object>) map;
        }
        throw new IllegalArgumentException("Expected object for " + fieldName);
    }

    @SuppressWarnings("unchecked")
    private List<Object> requireArray(Object value, String fieldName) {
        if (value instanceof List<?> list) {
            return (List<Object>) list;
        }
        throw new IllegalArgumentException("Expected array for " + fieldName);
    }

    private Object findValue(Map<String, Object> object, String... keys) {
        for (String key : keys) {
            if (object.containsKey(key)) {
                return object.get(key);
            }
        }
        return null;
    }

    private double numberValue(Map<String, Object> object, String... keys) {
        Object value = findValue(object, keys);
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        throw new IllegalArgumentException("Missing number: " + String.join("/", keys));
    }

    private int intValue(Map<String, Object> object, String... keys) {
        Object value = findValue(object, keys);
        if (value instanceof Number number) {
            return number.intValue();
        }
        throw new IllegalArgumentException("Missing integer: " + String.join("/", keys));
    }
}
