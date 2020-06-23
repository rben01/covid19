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
	const width = 600,
		height = 600;
	const pa = {
		width: width,
		height: height,
		axis: {
			outerMargins: {
				top: 3,
				bottom: 60,
				left: 40,
				right: 3,
			},
			innerMargin: 15,
			width: (null as unknown) as number,
			height: (null as unknown) as number,
			style: {
				strokeWidth: 1,
				tickLength: 6,
				axisColor: "black",
				gridlineColor: "#e4e4e4",
				labelTranslateX: (7 / 600) * width,
				labelTranslateY: (7 / 600) * height,
			},
		},
		colors: {
			scale: d3.scaleOrdinal().range(d3.schemeTableau10) as (
				arg0: string,
			) => string,
		},
	};

	pa.axis.width = pa.width - pa.axis.outerMargins.left;
	pa.axis.height = pa.height - pa.axis.outerMargins.bottom;

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
	.attr("width", plotAesthetics.width)
	.attr("height", plotAesthetics.height);
const chartArea = svg.append("g").classed("line-chart-area", true);

export function initializeLineGraph(
	allCovidData: AllCovidData,
	allGeoData: AllGeoData,
) {
	lineGraph.datum({ allCovidData, allGeoData });

	const location: WorldLocation = "usa";
	const count: CountMethod = "net";
	const caseType: CaseType = "cases";

	updateLineGraph(location, caseType, count, "first_date");
}

const outbreakCutoff: { [key in CaseType]: [CaseType, Number] } = {
	cases: ["cases", 100],
	cases_per_capita: ["cases", 100],
	deaths: ["deaths", 25],
	deaths_per_capita: ["deaths", 25],
};

function updateLineGraph(
	location: WorldLocation,
	caseType: CaseType,
	count: CountMethod,
	startFrom: StartFrom,
) {
	const {
		allCovidData,
		allGeoData,
	}: { allCovidData: AllCovidData; allGeoData: AllGeoData } = lineGraph.datum();

	const scopedCovidData = allCovidData[location];
	const scopedGeoData = allGeoData[location];

	const innerMargin = plotAesthetics.axis.innerMargin;
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
			plotAesthetics.axis.outerMargins.left,
			plotAesthetics.width - plotAesthetics.axis.outerMargins.right,
		];
		const lineRange = [axisRange[0] + innerMargin, axisRange[1] - innerMargin];
		if (startFrom === "first_date") {
			const {
				min_nonzero: _minDateStr,
				max: _maxDateStr,
			} = scopedCovidData.agg.net.date;

			const [minDate, maxDate]: Date[] = [_minDateStr, _maxDateStr].map(
				dateStrParser,
			);

			return {
				axisXScale: d3.scaleTime().domain([minDate, maxDate]).range(axisRange),
				lineXScale: d3.scaleTime().domain([minDate, maxDate]).range(lineRange),
				minXVal: minDate,
				maxXVal: maxDate,
			};
		} else {
			let maxXVal = -1;
			for (const feature of scopedGeoData.features) {
				const covidData = feature.covidData;
				const outBreakStartIndex = covidData.outbreak_cutoffs[caseType];
				const nDaysSinceOutbreak =
					covidData[caseType].length - outBreakStartIndex;
				if (nDaysSinceOutbreak > maxXVal) {
					maxXVal = nDaysSinceOutbreak;
				}
			}
			const minXVal = 0;
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

	const { min_nonzero: minYVal, max: maxYVal } = allCovidData[location].agg[count][
		caseType
	];

	const axisYScale = d3
		.scaleLog()
		.domain([minYVal, maxYVal])
		.range([plotAesthetics.axis.height, plotAesthetics.axis.outerMargins.top]);
	const lineYScale = d3
		.scaleLog()
		.domain([minYVal, maxYVal])
		.range([
			plotAesthetics.axis.height - innerMargin,
			plotAesthetics.axis.outerMargins.top + innerMargin,
		]);

	const {
		strokeWidth,
		axisColor,
		tickLength,
		gridlineColor,
	} = plotAesthetics.axis.style;

	const xTicks = axisXScale.ticks(d3.timeDay.every(7));
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
		.attr("x2", axisXScale(minXVal) - plotAesthetics.axis.style.tickLength)
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
		.attr("stroke", plotAesthetics.axis.style.gridlineColor)
		.attr("stroke-width", plotAesthetics.axis.style.strokeWidth);

	// Axis labels
	xAxis
		.selectAll()
		.data(xTicks)
		.join("text")
		.classed("x-axis-label", true)
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
				`translate(${
					lineXScale(d) + plotAesthetics.axis.style.labelTranslateX
				},${
					axisYScale(minYVal) +
					tickLength +
					plotAesthetics.axis.style.labelTranslateY
				}) rotate(-60)`,
		);
	yAxis
		.selectAll()
		.data(yTicks)
		.join("text")
		.classed("y-axis-label", true)
		.text((y: number) => {
			const firstDigit = +y.toString()[0];
			if (firstDigit <= 4 || firstDigit === 6) {
				return yFormatter(y);
			}
			return "";
		})
		.attr("x", axisXScale(minXVal) - plotAesthetics.axis.style.tickLength - 3)
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

	// Now for the actual data we want to plot
	const pathDrawer: (arg0: Point[]) => void = d3
		.line()
		.x((p: Point) => lineXScale(p.x))
		.y((p: Point) => lineYScale(p.y));

	const lines: Line[] = [];
	if (startFrom === "first_date") {
		for (const feature of scopedGeoData.features) {
			if (typeof feature.covidData === "undefined") {
				continue;
			}
			const thisLine = new Line(feature.properties.name);
			const dates: DateString[] = Object.keys(feature.covidData.date).sort();
			dates.forEach((dateStr: DateString, index) => {
				const value = feature.covidData[caseType][index];
				const scaledValue = lineYScale(value);
				if (scaledValue === null || isNaN(scaledValue)) {
					return;
				}
				thisLine.push({
					x: dateStrParser(dateStr),
					y: value,
				});
			});
			lines.push(thisLine);
		}
	} else {
	}

	chartArea
		.selectAll()
		.data(lines)
		.join("path")
		.attr("d", (l: Line) => pathDrawer(l.points))
		.attr("stroke-width", 1)
		.attr("fill-opacity", 0)
		.attr("stroke", (l: Line) => plotAesthetics.colors.scale(l.name))
		.attr("_name", (l: any) => l.name);
}
