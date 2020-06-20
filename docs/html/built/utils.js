export function isPerCapita(caseType) {
    return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}
export const dateStrParser = d3.timeParse("%Y-%m-%d");
export const getFormatter = (() => {
    const intFormatter = d3.format(",~s");
    const bigFloatFormatter = d3.format("~g");
    const smallFloatFormatter = d3.format(",.2f");
    const floatFormatter = (t) => t < 1 ? smallFloatFormatter(t) : bigFloatFormatter(t);
    return (count, caseType, smoothAvgDays) => {
        return (count === "net" && !isPerCapita(caseType)) ||
            (count === "dodd" && smoothAvgDays === 1)
            ? intFormatter
            : floatFormatter;
    };
})();
