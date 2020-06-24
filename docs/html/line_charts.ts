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

import { dateStrParser, getFormatter, isPerCapita } from "./utils.js";

type StartFrom = "first_date" | "outbreak";
type XAxisType = number | Date;
type Point = { x: XAxisType; y: number };
class Line {
	name: string;
	points: Point[];

	constructor(name: string) {
		this.name = name;
		this.points = [];
	}

	push(p: Point) {
		this.points.push(p);
	}
}

const plotAesthetics = (() => {
	const chartWidth = 600,
		chartHeight = 500;
	const outerMargins = {
		top: 3,
		bottom: 60,
		left: 40,
		right: 3,
	};
	const fullWidth = chartWidth + outerMargins.left + outerMargins.right;
	const fullHeight = chartHeight + outerMargins.top + outerMargins.bottom;
	const pa = {
		fullWidth,
		fullHeight,
		graph: {
			outerMargins,
			innerMargin: 15,
			width: chartWidth,
			height: chartHeight,
			axisStyle: {
				strokeWidth: 1,
				tickLength: 6,
				axisColor: "black",
				gridlineColor: "#e4e4e4",
				labelTranslateX: (7 / 500) * chartWidth,
				labelTranslateY: (7 / 500) * chartHeight,
			},
			line: {
				strokeWidth: 2,
			},
		},
		colors: {
			scale: d3.scaleOrdinal().range(d3.schemeTableau10) as (
				arg0: string,
			) => string,
		},
	};

	pa.graph.width = pa.fullWidth - pa.graph.outerMargins.left;
	pa.graph.height = pa.fullHeight - pa.graph.outerMargins.bottom;

	return pa;
})();

const lineGraph: {
	datum: (arg0?: {
		allCovidData: AllCovidData;
		allGeoData: AllGeoData;
	}) => {
		allCovidData: AllCovidData;
		allGeoData: AllGeoData;
	};
	[key: string]: any;
} = d3.select("#line-charts-section").append("div").attr("id", "line-chart");

const dateFormatter = d3.timeFormat("%b %-d");
const svg = lineGraph
	.append("svg")
	.attr("width", plotAesthetics.fullWidth)
	.attr("height", plotAesthetics.fullHeight);
const chartArea = svg.append("g").classed("line-chart-area", true);

export function initializeLineGraph(
	allCovidData: AllCovidData,
	allGeoData: AllGeoData,
) {
	lineGraph.datum({ allCovidData, allGeoData });

	const location: WorldLocation = "usa";
	const count: CountMethod = "dodd";
	const caseType: CaseType = "cases_per_capita";

	updateLineGraph(location, caseType, count, "first_date", 7);
}

function updateLineGraph(
	location: WorldLocation,
	caseType: CaseType,
	count: CountMethod,
	startFrom: StartFrom,
	smoothAvgDays: number,
) {
	const allGeoData: AllGeoData = lineGraph.datum().allGeoData;

	const scopedGeoData = allGeoData[location];

	// Construct the lines we will plot
	const nLines = 10;
	const lines: Line[] = [];

	const topNPlaces: [Feature, number][] = [];
	let cutoffValue = -Infinity;
	for (const feature of scopedGeoData.features) {
		if (typeof feature.covidData === "undefined") {
			continue;
		}
		const values = feature.covidData[count][caseType];
		const currentValue = values[values.length - 1];
		if (topNPlaces.length < nLines) {
			topNPlaces.push([feature, currentValue]);
			if (currentValue < cutoffValue) {
				cutoffValue = currentValue;
			}
		} else if (currentValue > cutoffValue) {
			const idxToReplace = topNPlaces.findIndex(
				([_, value]) => value === cutoffValue,
			);
			topNPlaces[idxToReplace] = [feature, currentValue];
			cutoffValue = Math.min(...topNPlaces.map(([_, value]) => value));
		}
	}

	if (startFrom === "first_date") {
		for (const [feature, _] of topNPlaces) {
			const thisLine = new Line(feature.properties.name);

			const covidData = feature.covidData;
			const dates: DateString[] = Object.keys(covidData.date).sort();
			const values = covidData[count][caseType];

			if (count === "dodd" && smoothAvgDays >= 2) {
				let sum = values.slice(0, smoothAvgDays - 1).reduce((a, b) => a + b);
				let prevValue = 0;
				for (let i = smoothAvgDays; i < values.length; ++i) {
					const dateStr = dates[i];
					const value = values[i];

					sum -= prevValue;
					sum += value;
					prevValue = values[i - smoothAvgDays + 1];

					const avg = sum / smoothAvgDays;
					thisLine.push({
						x: dateStrParser(dateStr),
						y: avg,
					});
				}
			} else {
				for (let i = 0; i < dates.length; ++i) {
					const dateStr = dates[i];
					const value = values[i];
					thisLine.push({
						x: dateStrParser(dateStr),
						y: value,
					});
				}
			}

			lines.push(thisLine);
		}
	} else {
		for (const [feature, _] of topNPlaces) {
			const thisLine = new Line(feature.properties.name);
			const covidData = feature.covidData;
			const values = covidData[count][caseType];
			const startIndex = covidData.outbreak_cutoffs[caseType];

			if (count === "dodd" && smoothAvgDays >= 2) {
				let sum = values
					.slice(startIndex, startIndex + smoothAvgDays - 1)
					.reduce((a, b) => a + b);
				let prevValue = 0;
				for (
					let i = Math.max(startIndex, smoothAvgDays);
					i < values.length;
					++i
				) {
					const value = values[i];

					sum -= prevValue;
					sum += value;
					prevValue = values[i - smoothAvgDays + 1];

					const avg = sum / smoothAvgDays;
					thisLine.push({
						x: i,
						y: avg,
					});
				}
			} else {
				for (let i = startIndex; i < values.length; ++i) {
					const value = values[i];
					thisLine.push({ x: i, y: value });
				}
			}

			lines.push(thisLine);
		}
	}

	const [minYVal, maxYVal] = (() => {
		let min = Infinity,
			max = -Infinity;
		for (let line of lines) {
			for (let point of line.points) {
				const y = point.y;
				if (0 < y && y < min) {
					min = y;
				} else if (y > max) {
					max = y;
				}
			}
		}
		return [min, max];
	})();

	const innerMargin = plotAesthetics.graph.innerMargin;
	const axisYScale = d3
		.scaleLog()
		.domain([minYVal, maxYVal])
		.range([plotAesthetics.graph.height, plotAesthetics.graph.outerMargins.top]);
	const lineYScale = d3
		.scaleLog()
		.domain([minYVal, maxYVal])
		.range([
			plotAesthetics.graph.height - innerMargin,
			plotAesthetics.graph.outerMargins.top + innerMargin,
		]);

	const {
		axisXScale,
		lineXScale,
		minXVal,
		maxXVal,
	}: {
		axisXScale: any;
		lineXScale: any;
		minXVal: XAxisType;
		maxXVal: XAxisType;
	} = (() => {
		const axisRange = [
			plotAesthetics.graph.outerMargins.left,
			plotAesthetics.fullWidth - plotAesthetics.graph.outerMargins.right,
		];
		const lineRange = [axisRange[0] + innerMargin, axisRange[1] - innerMargin];
		if (startFrom === "first_date") {
			const lineXs = lines.map(line => line.points.map(p => p.x));
			const minDate = lineXs
				.map(points => points[0])
				.reduce((a, b) => (a < b ? a : b));
			const maxDate = lineXs
				.map(points => points[points.length - 1])
				.reduce((a, b) => (a > b ? a : b));

			return {
				axisXScale: d3.scaleTime().domain([minDate, maxDate]).range(axisRange),
				lineXScale: d3.scaleTime().domain([minDate, maxDate]).range(lineRange),
				minXVal: minDate,
				maxXVal: maxDate,
			};
		} else {
			const minXVal = 0;
			const maxXVal = Math.max(
				...lines.map(line => line.points[line.points.length - 1].x as number),
			);
			return {
				axisXScale: d3
					.scaleLinear()
					.domain([minXVal, maxXVal])
					.range(axisRange),
				lineXScale: d3
					.scaleLinear()
					.domain([minXVal, maxXVal])
					.range(lineRange),
				minXVal: minXVal,
				maxXVal: maxXVal,
			};
		}
	})();

	const {
		strokeWidth,
		axisColor,
		tickLength,
		gridlineColor,
	} = plotAesthetics.graph.axisStyle;

	const xTicks =
		startFrom === "first_date"
			? axisXScale.ticks(d3.timeDay.every(7))
			: axisXScale.ticks(10);
	const yFormatter = getFormatter(count, caseType, 1);
	const yTicks = axisYScale.ticks(15);

	const xAxis = chartArea.append("g").classed("line-chart-x-axis", true);
	const yAxis = chartArea.append("g").classed("line-chart-y-axis", true);

	// Tick marks
	xAxis
		.selectAll()
		.data(xTicks)
		.join("line")
		.classed("x-axis-tick", true)
		.attr("x1", lineXScale)
		.attr("x2", lineXScale)
		.attr("y1", axisYScale(minYVal))
		.attr("y2", axisYScale(minYVal) + tickLength)
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth);
	yAxis
		.selectAll()
		.data(yTicks)
		.join("line")
		.classed("y-axis-tick", true)
		.attr("x1", axisXScale(minXVal))
		.attr("x2", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength)
		.attr("y1", lineYScale)
		.attr("y2", lineYScale)
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth);

	// Gridlines
	xAxis
		.selectAll()
		.data(xTicks)
		.join("line")
		.classed("x-axis-gridline", true)
		.attr("x1", lineXScale)
		.attr("x2", lineXScale)
		.attr("y1", axisYScale(minYVal))
		.attr("y2", axisYScale(maxYVal))
		.attr("stroke", gridlineColor)
		.attr("stroke-width", strokeWidth);
	yAxis
		.selectAll()
		.data(yTicks)
		.join("line")
		.classed("y-axis-gridline", true)
		.attr("x1", axisXScale(minXVal))
		.attr("x2", axisXScale(maxXVal))
		.attr("y1", lineYScale)
		.attr("y2", lineYScale)
		.attr("stroke", plotAesthetics.graph.axisStyle.gridlineColor)
		.attr("stroke-width", plotAesthetics.graph.axisStyle.strokeWidth);

	// Axis labels
	const xTickLabels = xAxis
		.selectAll()
		.data(xTicks)
		.join("text")
		.classed("x-axis-label", true)
		.attr("font-size", "70%");

	if (startFrom === "first_date") {
		xTickLabels
			.text((date: Date) => {
				const dayOfMonth = date.getDate();
				return dayOfMonth % 7 == 1 && dayOfMonth < 28
					? dateFormatter(date)
					: "";
			})
			.attr(
				"transform",
				(d: Date) =>
					`translate(${
						lineXScale(d) + plotAesthetics.graph.axisStyle.labelTranslateX
					},${
						axisYScale(minYVal) +
						tickLength +
						plotAesthetics.graph.axisStyle.labelTranslateY
					}) rotate(-60)`,
			)
			.attr("text-anchor", "end");
	} else {
		xTickLabels
			.text((daysSince: number) => {
				return daysSince % 5 == 0 ? daysSince : "";
			})
			.attr(
				"transform",
				(daysSince: number) =>
					`translate(${lineXScale(daysSince)},${
						axisYScale(minYVal) + tickLength + 13
					})`,
			)
			.attr("text-anchor", "middle");
	}

	yAxis
		.selectAll()
		.data(yTicks)
		.join("text")
		.classed("y-axis-label", true)
		.text((y: number) => {
			const yStr = yFormatter(y);
			const firstSigFigIndex = yStr.search(/[1-9]/);
			const firstSigFig = +yStr[firstSigFigIndex];
			if (firstSigFig <= 4 || firstSigFig === 6) {
				return yFormatter(y);
			}
			return "";
		})
		.attr("x", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength - 3)
		.attr("y", lineYScale)
		.attr("text-anchor", "end")
		.attr("dominant-baseline", "middle")
		.attr("font-size", "70%");

	// Axes themselves
	const axisLine = d3
		.line()
		.x((p: [number, number]) => axisXScale(p[0]))
		.y((p: [number, number]) => axisYScale(p[1]));
	chartArea
		.selectAll()
		.data([
			[
				[minXVal, minYVal],
				[minXVal, maxYVal],
				[maxXVal, maxYVal],
				[maxXVal, minYVal],
				[minXVal, minYVal],
			],
		])
		.join("path")
		.attr("d", axisLine)
		.attr("fill-opacity", 0)
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth);

	// Finally, draw the lines
	// Now for the actual data we want to plot
	const pathDrawer: (arg0: Point[]) => void = d3
		.line()
		.x((p: Point) => lineXScale(p.x))
		.y((p: Point) => lineYScale(p.y))
		.defined((p: Point) => lineYScale(p.y) > 0)
		.curve(d3.curveMonotoneX);

	console.log(lines);
	chartArea
		.selectAll()
		.data(lines)
		.join("path")
		.attr("d", (l: Line) => pathDrawer(l.points))
		.attr("stroke-width", plotAesthetics.graph.line.strokeWidth)
		.attr("fill-opacity", 0)
		.attr("stroke", (l: Line) => plotAesthetics.colors.scale(l.name))
		.attr("_name", (l: any) => l.name);
}
