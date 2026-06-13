import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class SimpleJsonParser {

    private final String json;
    private int position;

    private SimpleJsonParser(String json) {
        this.json = json;
    }

    static Object parse(String json) {
        SimpleJsonParser parser = new SimpleJsonParser(json);
        Object value = parser.parseValue();
        parser.skipWhitespace();
        if (!parser.isAtEnd()) {
            throw parser.error("Unexpected trailing content");
        }
        return value;
    }

    private Object parseValue() {
        skipWhitespace();
        if (isAtEnd()) {
            throw error("Unexpected end of JSON");
        }

        char current = json.charAt(position);
        return switch (current) {
            case '{' -> parseObject();
            case '[' -> parseArray();
            case '"' -> parseString();
            case 't' -> parseLiteral("true", Boolean.TRUE);
            case 'f' -> parseLiteral("false", Boolean.FALSE);
            case 'n' -> parseLiteral("null", null);
            default -> {
                if (current == '-' || Character.isDigit(current)) {
                    yield parseNumber();
                }
                throw error("Unexpected character '" + current + "'");
            }
        };
    }

    private Map<String, Object> parseObject() {
        expect('{');
        Map<String, Object> object = new LinkedHashMap<>();
        skipWhitespace();
        if (peek('}')) {
            position++;
            return object;
        }

        while (true) {
            skipWhitespace();
            String key = parseString();
            skipWhitespace();
            expect(':');
            object.put(key, parseValue());
            skipWhitespace();
            if (peek('}')) {
                position++;
                return object;
            }
            expect(',');
        }
    }

    private List<Object> parseArray() {
        expect('[');
        List<Object> array = new ArrayList<>();
        skipWhitespace();
        if (peek(']')) {
            position++;
            return array;
        }

        while (true) {
            array.add(parseValue());
            skipWhitespace();
            if (peek(']')) {
                position++;
                return array;
            }
            expect(',');
        }
    }

    private String parseString() {
        expect('"');
        StringBuilder builder = new StringBuilder();
        while (!isAtEnd()) {
            char current = json.charAt(position++);
            if (current == '"') {
                return builder.toString();
            }
            if (current == '\\') {
                builder.append(parseEscape());
            } else {
                builder.append(current);
            }
        }
        throw error("Unterminated string");
    }

    private char parseEscape() {
        if (isAtEnd()) {
            throw error("Unterminated escape sequence");
        }
        char escaped = json.charAt(position++);
        return switch (escaped) {
            case '"', '\\', '/' -> escaped;
            case 'b' -> '\b';
            case 'f' -> '\f';
            case 'n' -> '\n';
            case 'r' -> '\r';
            case 't' -> '\t';
            case 'u' -> parseUnicodeEscape();
            default -> throw error("Unsupported escape sequence");
        };
    }

    private char parseUnicodeEscape() {
        if (position + 4 > json.length()) {
            throw error("Invalid unicode escape");
        }
        String hex = json.substring(position, position + 4);
        position += 4;
        try {
            return (char) Integer.parseInt(hex, 16);
        } catch (NumberFormatException exception) {
            throw error("Invalid unicode escape");
        }
    }

    private Object parseLiteral(String literal, Object value) {
        if (!json.startsWith(literal, position)) {
            throw error("Invalid literal");
        }
        position += literal.length();
        return value;
    }

    private Number parseNumber() {
        int start = position;
        if (peek('-')) {
            position++;
        }
        consumeDigits();
        if (peek('.')) {
            position++;
            consumeDigits();
        }
        if (peek('e') || peek('E')) {
            position++;
            if (peek('+') || peek('-')) {
                position++;
            }
            consumeDigits();
        }

        String numberText = json.substring(start, position);
        try {
            if (numberText.contains(".") || numberText.contains("e") || numberText.contains("E")) {
                return Double.parseDouble(numberText);
            }
            return Long.parseLong(numberText);
        } catch (NumberFormatException exception) {
            throw error("Invalid number");
        }
    }

    private void consumeDigits() {
        int start = position;
        while (!isAtEnd() && Character.isDigit(json.charAt(position))) {
            position++;
        }
        if (start == position) {
            throw error("Expected digit");
        }
    }

    private void expect(char expected) {
        skipWhitespace();
        if (isAtEnd() || json.charAt(position) != expected) {
            throw error("Expected '" + expected + "'");
        }
        position++;
    }

    private boolean peek(char expected) {
        return !isAtEnd() && json.charAt(position) == expected;
    }

    private void skipWhitespace() {
        while (!isAtEnd() && Character.isWhitespace(json.charAt(position))) {
            position++;
        }
    }

    private boolean isAtEnd() {
        return position >= json.length();
    }

    private IllegalArgumentException error(String message) {
        return new IllegalArgumentException(message + " at position " + position);
    }
}
