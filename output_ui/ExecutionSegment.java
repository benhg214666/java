public record ExecutionSegment(int start, int end) {

    public ExecutionSegment {
        if (end < start) {
            throw new IllegalArgumentException("segment end must be greater than or equal to start");
        }
    }

    public int duration() {
        return end - start;
    }
}
