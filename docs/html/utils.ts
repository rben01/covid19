import { CaseType, CountMethod } from "./types";

declare const d3: any;

export function isPerCapita(caseType: CaseType) {
	return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}

export const dateStrParser: (_: string) => Date = d3.timeParse("%Y-%m-%d");
export const getFormatter: (
	count: CountMethod,
	caseType: CaseType,
	smoothAvgDays: number,
) => (_: number) => string = (() => {
	const bigFloatFormatter = d3.format("~g");
	const smallFloatFormatter = d3.format(",.2r");
	const tinyFloatFormatter = d3.format(".2~e");
	const floatFormatter = (t: number) =>
		t < 1e-2
			? tinyFloatFormatter(t)
			: t < 1
			? smallFloatFormatter(t)
			: bigFloatFormatter(t);
	const intFormatter = (t: number) =>
		t < 1 ? floatFormatter(t) : d3.format(",~s")(t);

	return (count: CountMethod, caseType: CaseType, smoothAvgDays: number) => {
		return (count === "net" && !isPerCapita(caseType)) ||
			(count === "dodd" && smoothAvgDays === 1)
			? intFormatter
			: floatFormatter;
	};
})();
