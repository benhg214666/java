public record EvaluationSummary(
        double hardDeadlineMissRate,
        double softDeadlineMissRate,
        double sporadicValueRate,
        double generatorCost,
        double marketRevenue,
        double objectiveValue,
        int constraintViolationCount,
        boolean verificationPassed
) {

    public String toDisplayText() {
        return "Evaluation Summary\n"
                + "Hard deadline miss rate: " + format(hardDeadlineMissRate) + "\n"
                + "Soft deadline miss rate: " + format(softDeadlineMissRate) + "\n"
                + "Sporadic value rate: " + format(sporadicValueRate) + "\n"
                + "Generator cost: " + format(generatorCost) + "\n"
                + "Market revenue: " + format(marketRevenue) + "\n"
                + "Objective value: " + format(objectiveValue) + "\n"
                + "Constraint violations: " + constraintViolationCount + "\n"
                + "Verification passed: " + verificationPassed;
    }

    private String format(double value) {
        return String.format("%.6f", value);
    }
}
