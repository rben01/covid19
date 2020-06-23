export function isPerCapita(caseType) {
    return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}
export const dateStrParser = d3.timeParse("%Y-%m-%d");
export const getFormatter = (() => {
    const bigFloatFormatter = d3.format("~g");
    const smallFloatFormatter = d3.format(",.2f");
    const floatFormatter = (t) => t < 1 ? smallFloatFormatter(t) : bigFloatFormatter(t);
    const intFormatter = (t) => t < 1 ? smallFloatFormatter(t) : d3.format(",~s")(t);
    return (count, caseType, smoothAvgDays) => {
        return (count === "net" && !isPerCapita(caseType)) ||
            (count === "dodd" && smoothAvgDays === 1)
            ? intFormatter
            : floatFormatter;
    };
})();
