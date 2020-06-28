export const MS_PER_DAY = 86400 * 1000;
export const EPSILON = 1e-8;
export function isPerCapita(caseType) {
    return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}
export const dateStrParser = d3.timeParse("%Y-%m-%d");
export function getFormatter(count, caseType, movingAvgDays) {
    const bigFloatFormatter = d3.format(".3~s");
    const smallFloatFormatter = d3.format(",.3~r");
    const tinyFloatFormatter = d3.format(".2~e");
    const floatFormatter = (t) => t < EPSILON
        ? "0.0"
        : t < 1e-2
            ? tinyFloatFormatter(t)
            : t < 1
                ? smallFloatFormatter(t)
                : bigFloatFormatter(t);
    const intFormatter = (t) => t < 1 ? floatFormatter(t) : d3.format(",.4~s")(t);
    return count === "net" || (count === "dodd" && movingAvgDays === 1)
        ? intFormatter
        : floatFormatter;
}
export function movingAvg(values, movingAvgDays, endIndex) {
    const startIndex = Math.max(endIndex - movingAvgDays + 1, 0);
    return (values.slice(startIndex, endIndex + 1).reduce((a, b) => {
        if (!a) {
            return b;
        }
        if (!b) {
            return a;
        }
        return a + b;
    }) / movingAvgDays);
}
