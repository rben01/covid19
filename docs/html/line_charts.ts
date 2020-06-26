declare const d3: any;
import {
	AllCovidData,
	AllGeoData,
	CaseType,
	CountMethod,
	DateString,
	Feature,
	WorldLocation,
} from "./types.js";
import { dateStrParser, EPSILON, getFormatter, MS_PER_DAY } from "./utils.js";

type Affliction = "cases" | "deaths";
type Accumulation = "total" | "per_capita";
type StartFrom = "first_date" | "outbreak";

type XAxisType = number | Date;
type Point = { x: XAxisType; y: number };
class Line {
	name: string;
	code: string;
	points: Point[];

	constructor(name: string, code: string) {
		this.name = name;
		this.code = code;
		this.points = [];
	}

	push(p: Point) {
		this.points.push(p);
	}
}

const plotAesthetics = (() => {
	const chartWidth = 500,
		chartHeight = 500;
	const outerMargins = {
		top: 6,
		bottom: 100,
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
			scaleFactory: () =>
				d3.scaleOrdinal().range(d3.schemeTableau10) as (_: string) => string,
			scale: d3.scaleOrdinal().range(d3.schemeTableau10) as (_: string) => string,
		},
	};

	pa.graph.width = pa.fullWidth - pa.graph.outerMargins.left;
	pa.graph.height = pa.fullHeight - pa.graph.outerMargins.bottom;

	return pa;
})();

const dateFormatter = d3.timeFormat("%b %-d");

type LineGraphContainer = {
	datum: (arg0?: {
		allCovidData?: AllCovidData;
		allGeoData?: AllGeoData;
		location?: WorldLocation;
		count?: CountMethod;
		affliction?: Affliction;
		accumulation?: Accumulation;
		startFrom?: StartFrom;
	}) => {
		allCovidData: AllCovidData;
		allGeoData: AllGeoData;
		location: WorldLocation;
		count: CountMethod;
		affliction: Affliction;
		accumulation: Accumulation;
		startFrom: StartFrom;
	};
	[key: string]: any;
};

export function initializeLineGraph(
	allCovidData: AllCovidData,
	allGeoData: AllGeoData,
) {
	const location: WorldLocation = "usa";
	const count: CountMethod = "dodd";
	const affliction: Affliction = "cases";
	const accumulation: Accumulation = "per_capita";
	const startFrom: StartFrom = "first_date";

	const datum = {
		allCovidData,
		allGeoData,
		location,
		count,
		affliction,
		accumulation,
		startFrom,
	};

	const lineGraphContainer: LineGraphContainer = d3
		.select("#line-charts-section")
		.append("div");
	lineGraphContainer.datum(datum);

	const checkboxGroup = lineGraphContainer
		.append("div")
		.classed("checkbox-table", true);
	const checkboxTable = checkboxGroup.append("table");
	checkboxTable
		.append("tr")
		.selectAll()
		.data(["Location", "Count", "Cases/Deaths", "Total/Per 100k"])
		.join("th")
		.text((d: string) => d)
		.attr("colspan", 2);
	const rows: {
		key: "location" | "count" | "affliction" | "accumulation" | "startFrom";
		value: string;
		name: string;
	}[][] = [
		[
			{ key: "location", value: "usa", name: "USA" },
			{ key: "count", value: "dodd", name: "Daily Increase" },
			{ key: "affliction", value: "cases", name: "Cases" },
			{ key: "accumulation", value: "per_capita", name: "Per 100k Residents" },
		],
		[
			{ key: "location", value: "world", name: "World" },
			{ key: "count", value: "net", name: "Cases Over Time" },
			{ key: "affliction", value: "deaths", name: "Deaths" },
			{ key: "accumulation", value: "total", name: "Total" },
		],
	];
	for (const row of rows) {
		const tr = checkboxTable.append("tr");
		for (const col of row) {
			const { key, value, name } = col as {
				key: "location" | "count" | "affliction" | "accumulation";
				value: string;
				name: string;
			};
			tr.append("td").text(name);
			tr.append("td")
				.append("input")
				.property("checked", value === datum[key])
				.attr("type", "radio")
				.property("name", `${key}-line-chart`)
				.on("change", function (d: any) {
					const datum = lineGraph.datum();
					datum[key] = value as never; // ?? some TS weirdness;
					updateLineGraph(lineGraphContainer, 7, { refreshColors: true });
				});
		}
	}

	const lineGraph = lineGraphContainer.append("div").classed("line-chart", true);

	const svg = lineGraph
		.append("svg")
		.attr("width", plotAesthetics.fullWidth)
		.attr("height", plotAesthetics.fullHeight);
	const chartArea = svg.append("g").classed("line-chart-area", true);
	chartArea.append("g").classed("line-chart-x-axis", true);
	chartArea.append("g").classed("line-chart-y-axis", true);

	lineGraphContainer
		.append("div")
		.classed("line-chart-legend-container", true)
		.append("table")
		.classed("line-chart-legend", true)
		.append("tr")
		.append("th")
		.attr("colspan", 3);

	updateLineGraph(lineGraphContainer, 7);
}

function updateLineGraph(
	lineGraphContainer: LineGraphContainer,
	smoothAvgDays: number,
	{ refreshColors }: { refreshColors: Boolean } = { refreshColors: false },
) {
	const {
		location,
		count,
		affliction,
		accumulation,
		allGeoData,
		startFrom,
	} = lineGraphContainer.datum();

	const lineGraph = lineGraphContainer.selectAll(".line-chart");

	if (refreshColors) {
		plotAesthetics.colors.scale = plotAesthetics.colors.scaleFactory();
	}

	const scopedGeoData = allGeoData[location];

	const caseType = (accumulation === "per_capita"
		? `${affliction}_per_capita`
		: affliction) as CaseType;

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
			const thisLine = new Line(feature.properties.name, feature.properties.code);

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
			const thisLine = new Line(feature.properties.name, feature.properties.code);
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

	// Sort descending by latest data point
	lines.sort(
		(l1, l2) =>
			l2.points[l2.points.length - 1].y - l1.points[l1.points.length - 1].y,
	);

	const [minYVal, maxYVal] = (() => {
		let min = Infinity,
			max = -Infinity;
		for (let line of lines) {
			for (let point of line.points) {
				const y = point.y;
				if (EPSILON < y && y < min) {
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
	const yFormatter = getFormatter(count, caseType, smoothAvgDays);
	const yTicks = axisYScale.ticks(15);

	const chartArea = lineGraph.selectAll(".line-chart-area");
	const xAxis = chartArea.selectAll(".line-chart-x-axis");
	const yAxis = chartArea.selectAll(".line-chart-y-axis");

	// Tick marks
	xAxis
		.selectAll(".x-axis-tick")
		.data(xTicks)
		.join(
			(enter: any) =>
				enter
					.append("line")
					.classed("x-axis-tick", true)
					.attr("stroke", axisColor)
					.attr("stroke-width", strokeWidth),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
		.attr("x1", lineXScale)
		.attr("x2", lineXScale)
		.attr("y1", axisYScale(minYVal))
		.attr("y2", axisYScale(minYVal) + tickLength);
	yAxis
		.selectAll(".y-axis-tick")
		.data(yTicks)
		.join(
			(enter: any) =>
				enter
					.append("line")
					.classed("y-axis-tick", true)
					.attr("stroke", axisColor)
					.attr("stroke-width", strokeWidth),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
		.attr("x1", axisXScale(minXVal))
		.attr("x2", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength)
		.attr("y1", lineYScale)
		.attr("y2", lineYScale);

	// Gridlines
	xAxis
		.selectAll(".x-axis-gridline")
		.data(xTicks)
		.join(
			(enter: any) =>
				enter
					.append("line")
					.classed("x-axis-gridline", true)
					.attr("stroke", gridlineColor)
					.attr("stroke-width", strokeWidth),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
		.attr("x1", lineXScale)
		.attr("x2", lineXScale)
		.attr("y1", axisYScale(minYVal))
		.attr("y2", axisYScale(maxYVal));
	yAxis
		.selectAll(".y-axis-gridline")
		.data(yTicks)
		.join(
			(enter: any) =>
				enter
					.append("line")
					.classed("y-axis-gridline", true)
					.attr("stroke", plotAesthetics.graph.axisStyle.gridlineColor)
					.attr("stroke-width", plotAesthetics.graph.axisStyle.strokeWidth),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
		.attr("x1", axisXScale(minXVal))
		.attr("x2", axisXScale(maxXVal))
		.attr("y1", lineYScale)
		.attr("y2", lineYScale);

	// Axis labels
	const xTickLabels = xAxis
		.selectAll(".x-axis-label")
		.data(xTicks)
		.join(
			(enter: any) =>
				enter
					.append("text")
					.classed("x-axis-label", true)
					.attr("font-size", "70%"),
			(update: any) => update,
			(exit: any) => exit.remove(),
		);
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
		.selectAll(".y-axis-label")
		.data(yTicks)
		.join(
			(enter: any) =>
				enter
					.append("text")
					.classed("y-axis-label", true)
					.attr("text-anchor", "end")
					.attr("dominant-baseline", "middle")
					.attr("font-size", "70%"),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
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
		.attr("y", lineYScale);

	// Finally, draw the lines
	// Now for the actual data we want to plot
	const pathDrawer: (arg0: Point[]) => void = d3
		.line()
		.x((p: Point) => lineXScale(p.x))
		.y((p: Point) => lineYScale(p.y))
		.defined((p: Point) => p.y > EPSILON)
		.curve(d3.curveMonotoneX);

	chartArea
		.selectAll(".chart-line")
		.data(lines)
		.join(
			(enter: any) =>
				enter
					.append("path")
					.classed("chart-line", true)
					.attr("stroke-width", plotAesthetics.graph.line.strokeWidth)
					.attr("fill-opacity", 0),
			(update: any) => update,
			(exit: any) => exit.remove(),
		)
		.attr("d", (l: Line) => pathDrawer(l.points))
		.attr("stroke", (l: Line) => plotAesthetics.colors.scale(l.code));

	const legend = lineGraphContainer.selectAll(".line-chart-legend");
	// Axes themselves; also a region for catching mouse events
	function getInfoFromXVal(x: XAxisType) {
		let xVal: XAxisType, xStr: string;
		if (startFrom === "first_date") {
			x = x as Date;
			const roundedXVal = new Date(
				Math.round(x.getTime() / MS_PER_DAY) * MS_PER_DAY,
			);
			const year = roundedXVal.getUTCFullYear();
			const month = roundedXVal.getUTCMonth();
			const date = roundedXVal.getUTCDate();

			xVal = new Date(year, month, date);
			if (xVal < minXVal) {
				xVal = minXVal;
			} else if (xVal > maxXVal) {
				xVal = maxXVal;
			}
			xStr = dateFormatter(xVal);
		} else {
			x = x as number;
			xVal = Math.round(x);
			if (xVal < minXVal) {
				xVal = minXVal;
			} else if (xVal > maxXVal) {
				xVal = maxXVal;
			}
			xStr = `${xVal} days since`;
		}

		return { xVal, xStr };
	}

	const mainChartArea = chartArea.append("g");
	mainChartArea
		.selectAll(".chart-region")
		.data([
			{
				x: axisXScale(minXVal),
				y: axisYScale(maxYVal),
				width: axisXScale(maxXVal) - axisXScale(minXVal),
				height: axisYScale(minYVal) - axisYScale(maxYVal),
			},
		])
		.join("rect")
		.classed("chart-region", true)
		.attr("x", (d: any) => d.x)
		.attr("y", (d: any) => d.y)
		.attr("width", (d: any) => d.width)
		.attr("height", (d: any) => d.height)
		.attr("fill-opacity", 0)
		.attr("stroke", axisColor)
		.attr("stroke-width", strokeWidth)
		.on("mousemove", function (this: Node) {
			const mouseXScreen = d3.mouse(this)[0];
			const mouseXVal = lineXScale.invert(mouseXScreen);

			const { xVal, xStr: headerStr } = getInfoFromXVal(mouseXVal);

			const values = lines.map(line => {
				let prevDist = Infinity;
				let prevY = NaN;
				for (const point of line.points) {
					const dist = Math.abs(
						startFrom === "first_date"
							? (point.x as Date).getTime() - (xVal as Date).getTime()
							: (point.x as number) - (xVal as number),
					);
					if (dist > prevDist) {
						return prevY;
					}

					prevDist = dist;
					prevY = point.y;
				}
				return prevY;
			});

			legend
				.selectAll("td .legend-value")
				.text((_: any, i: number) => yFormatter(values[i]));

			legend.selectAll("tr th").text(headerStr);

			const hoverLineX = lineXScale(xVal);

			mainChartArea
				.selectAll(".line-chart-hover-line")
				.data([0])
				.join((enter: any) =>
					enter
						.insert("line", "rect.chart-region")
						.classed("line-chart-hover-line", true)
						.attr("stroke", "#444")
						.attr("stroke-width", 1.5)
						.attr("stroke-dasharray", "4 4"),
				)
				.attr("x1", hoverLineX)
				.attr("x2", hoverLineX)
				.attr("y1", axisYScale(minYVal))
				.attr("y2", axisYScale(maxYVal));
		})
		.on("mouseout", function (this: Node) {
			const values = lines.map(line => line.points[line.points.length - 1].y);
			legend
				.selectAll("td.legend-value")
				.text((_: any, i: number) => yFormatter(values[i]));
			mainChartArea.selectAll(".line-chart-hover-line").remove();
		});

	const headerStr = getInfoFromXVal(maxXVal).xStr;
	legend.selectAll("tr th").text(headerStr);

	legend
		.selectAll("tr.legend-data-row")
		.data(lines)
		.join("tr")
		.classed("legend-data-row", true)
		.each(function (this: Node, line: Line) {
			const row = d3.select(this);
			const { name, code } = line;
			const rowData = [
				{ type: "color", data: plotAesthetics.colors.scale(code) },
				{ type: "name", data: name },
				{
					type: "number",
					data: yFormatter(line.points[line.points.length - 1].y),
				},
			];
			row.selectAll("td")
				.data(rowData)
				.join("td")
				.classed("color-cell", true)
				.each(function (
					this: Node,
					d: { type: "color" | "name" | "number"; data: string },
				) {
					const td = d3.select(this);
					if (d.type === "color") {
						const color = d.data;
						td.selectAll(".legend-color-square")
							.data([color])
							.join((enter: any) =>
								enter
									.append("div")
									.classed("legend-color-square", true)
									.classed("legend-item", true),
							)
							.style("background-color", (c: string) => c);
					} else if (d.type === "name") {
						const name = d.data;
						td.selectAll(".legend-label")
							.data([name])
							.join((enter: any) =>
								enter
									.append("span")
									.classed("legend-label", true)
									.classed("legend-item", true),
							)
							.text((t: string) => t);
					} else if (d.type === "number") {
						const value = d.data;
						td.selectAll(".legend-value")
							.data([value])
							.join((enter: any) =>
								enter
									.append("span")
									.classed("legend-value", true)
									.classed("legend-item", true),
							)
							.text((t: string) => t);
					}
				});
		});
}
