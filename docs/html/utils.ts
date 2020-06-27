import { CaseType, CountMethod } from "./types";

declare const d3: any;

export const MS_PER_DAY = 86400 * 1000;
export const EPSILON = 1e-8;

export function isPerCapita(caseType: CaseType) {
	return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}

export const dateStrParser: (_: string) => Date = d3.timeParse("%Y-%m-%d");

export function getFormatter(
	count: CountMethod,
	caseType: CaseType,
	movingAvgDays: number,
): (_: number) => string {
	const bigFloatFormatter = d3.format(".3~s");
	const smallFloatFormatter = d3.format(",.3~r");
	const tinyFloatFormatter = d3.format(".2~e");
	const floatFormatter = (t: number) =>
		t < EPSILON
			? "0.0"
			: t < 1e-2
			? tinyFloatFormatter(t)
			: t < 1
			? smallFloatFormatter(t)
			: bigFloatFormatter(t);
	const intFormatter = (t: number) =>
		t < 1 ? floatFormatter(t) : d3.format(",.4~s")(t);

	return count === "net" || (count === "dodd" && movingAvgDays === 1)
		? intFormatter
		: floatFormatter;
}
