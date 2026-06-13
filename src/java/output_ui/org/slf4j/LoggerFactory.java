package org.slf4j;

import java.util.logging.Level;
import java.util.regex.Matcher;

public final class LoggerFactory {

    private LoggerFactory() {
    }

    public static Logger getLogger(Class<?> loggerClass) {
        return new JulLogger(java.util.logging.Logger.getLogger(loggerClass.getName()));
    }

    private record JulLogger(java.util.logging.Logger delegate) implements Logger {

        @Override
        public void info(String message, Object... arguments) {
            delegate.log(Level.INFO, format(message, arguments));
        }

        @Override
        public void error(String message, Object... arguments) {
            Throwable throwable = extractThrowable(arguments);
            if (throwable == null) {
                delegate.log(Level.SEVERE, format(message, arguments));
            } else {
                delegate.log(Level.SEVERE, format(message, arguments), throwable);
            }
        }

        private String format(String message, Object... arguments) {
            String formatted = message;
            int usableArguments = arguments.length;
            if (extractThrowable(arguments) != null) {
                usableArguments--;
            }
            for (int index = 0; index < usableArguments; index++) {
                formatted = formatted.replaceFirst("\\{}", Matcher.quoteReplacement(String.valueOf(arguments[index])));
            }
            return formatted;
        }

        private Throwable extractThrowable(Object... arguments) {
            if (arguments.length == 0) {
                return null;
            }
            Object lastArgument = arguments[arguments.length - 1];
            return lastArgument instanceof Throwable throwable ? throwable : null;
        }
    }
}
