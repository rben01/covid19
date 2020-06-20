declare const d3: any;
import {
	AllCovidData,
	AllGeoData,
	CaseType,
	CountMethod,
	DataGroup,
	DateString,
	Feature,
	PlotInfo,
	Scope,
	ScopedCovidData,
	ScopedGeoData,
	SCOPES,
	WorldLocation,
} from "./types.js";

import { dateStrParser, getFormatter } from "./utils.js";

type StartFrom = "first_date" | "outbreak";

const plotAesthetics = (() => {
	const pa = {
		width: 600,
		height: 600,
		axis: {
			margins: {
				bottom: 60,
				left: 30,
			},
			width: (null as unknown) as number,
			height: (null as unknown) as number,
			style: {
				strokeWidth: 1,
				tickLength: 6,
				axisColor: "black",
				gridlineColor: "#888",
			},
		},
		colors: {
			scale: d3.schemeTableau10 as string[],
		},
	};

	pa.axis.width = pa.width - pa.axis.margins.left;
	pa.axis.height = pa.height - pa.axis.margins.bottom;

	return pa;
})();

const lineGraph = d3
	.select("#line-charts-section")
	.append("div")
	.attr("id", "line-chart");

function updateLineGraph(
	lineGraph: any,
	location: WorldLocation,
	caseType: CaseType,
	count: CountMethod,
	startFrom: StartFrom,
) {}

const dateFormatter = d3.timeFormat("%b %-d");

export function initializeLineGraph(
	allCovidData: AllCovidData,
	geoCovidData: AllGeoData,
) {
	lineGraph.datum({ allCovidData, geoCovidData });

	const location: WorldLocation = "usa";
	const count: CountMethod = "dodd";
	const caseType: CaseType = "cases";

	// const xAxis = d3
	// 	.axisBottom(xScale)
	// 	.tickValues(xTicks)
	// 	.tickFormat((date: Date) => {
	// 		const dayOfMonth = date.getDate();
	// 		if (dayOfMonth % 7 == 1 && dayOfMonth < 28) {
	// 			return dateFormatter(date);
	// 		}
	// 		return "";
	// 	});

	// const yFormatter = getFormatter(count, caseType, 1);
	// const yAxis = d3
	// 	.axisLeft(yScale)
	// 	.ticks(6)
	// 	.tickFormat((n: number) => {
	// 		const firstDigit = +`${n}`[0];

	// 		if (firstDigit <= 4 || firstDigit % 2 === 0) {
	// 			return yFormatter(n);
	// 		}
	// 		return "";
	// 	});

	const svg = lineGraph
		.append("svg")
		.attr("width", plotAesthetics.width)
		.attr("height", plotAesthetics.height);
	const chartArea = svg.append("g").classed("line-chart-area", true);

	const { min_nonzero: _minDateStr, max: _maxDateStr } = allCovidData[
		location
	].agg.net.date;
	const { min_nonzero: minVal, max: maxVal } = allCovidData[location].agg.net[
		caseType
	];

	const [minDate, maxDate] = [_minDateStr, _maxDateStr].map(dateStrParser);

	const xScale = d3
		.scaleTime()
		.domain([minDate, maxDate])
		.range([plotAesthetics.axis.margins.left, plotAesthetics.width]);
	const yScale = d3
		.scaleLog()
		.domain([minVal, maxVal])
		.range([plotAesthetics.axis.height, 0]);

	const {
		strokeWidth,
		axisColor,
		tickLength,
		gridlineColor,
	} = plotAesthetics.axis.style;

	const xTicks = xScale.ticks(d3.timeDay.every(7));
	const xAxis = chartArea.append("g").classed("line-chart-x-axis", true);
	xAxis
		.append("line")
		.attr("x1", xScale(minDate))
		.attr("x2", xScale(maxDate))
		.attr("y1", yScale(minVal))
		.attr("y2", yScale(minVal))
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth);
	xAxis
		.selectAll()
		.data(xTicks)
		.join("line")
		.attr("x1", xScale)
		.attr("x2", xScale)
		.attr("y1", yScale(minVal))
		.attr("y2", yScale(minVal) + tickLength)
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth);
	xAxis
		.selectAll()
		.data(xTicks)
		.join("text")
		.text((date: Date) => {
			const dayOfMonth = date.getDate();
			if (dayOfMonth % 7 == 1 && dayOfMonth < 28) {
				return dateFormatter(date);
			}
			return "";
		})
		.attr("text-anchor", "end")
		.attr("font-size", "70%")
		.attr(
			"transform",
			(d: Date) =>
				`translate(${xScale(d) + 7},${
					yScale(minVal) + tickLength + 7
				}) rotate(-60)`,
		);
}
