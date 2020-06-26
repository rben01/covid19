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
	WORLD_LOCATIONS,
	COUNT_METHODS,
} from "./types.js";
import { dateStrParser, isPerCapita } from "./utils.js";

const MS_PER_DAY = 86400 * 1000;

const plotAesthetics = Object.freeze(
	(() => {
		const pa = {
			width: { usa: 500, world: 500 },
			height: { usa: 325, world: 300 },
			colors: {
				scale: (t: number) => d3.interpolateCividis(1 - t),
				nSteps: 101,
				missing: "#dadada",
				zero: "#ddc",
			},
			map: {
				pad: 10,
				borderWidth: 1,
				originX: NaN,
				originY: NaN,
				maxZoom: { usa: 4, world: 7 },
				zoomTransition: d3.transition().duration(500),
			},
			legend: {
				padLeft: 20,
				barWidth: 15,
				padRight: 20,
				height: { usa: 250, world: 230 },
				gradientID: "verticalLegendGradient",
			},
			title: {
				height: 40,
			},

			mapWidth: {} as { usa: number; world: number },
			mapHeight: {} as { usa: number; world: number },
		};

		pa.map.originX = pa.map.pad;
		pa.map.originY = pa.title.height + pa.map.pad;

		Object.keys(pa.width).forEach((key: string) => {
			const scope = key as WorldLocation;

			pa.mapWidth[scope] =
				pa.width[scope] -
				pa.map.originX -
				(pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight) -
				pa.map.pad;
		});

		Object.keys(pa.height).forEach((key: string) => {
			const scope = key as WorldLocation;
			pa.mapHeight[scope] = pa.height[scope] - pa.map.originY - pa.map.pad;
		});
		return pa;
	})(),
);

class PlaybackInfo {
	static speeds = [0.25, 0.5, 1, 2, 4];
	static defaultSpeed = 1;

	timer?: number;
	isPlaying: Boolean;
	selectedIndex: number;
	timerStartDate?: Date;
	timerElapsedTimeProptn: number;

	get baseIntervalMS(): number {
		return 1000;
	}

	get currentIntervalMS(): number {
		return this.baseIntervalMS / PlaybackInfo.speeds[this.selectedIndex];
	}

	constructor() {
		this.isPlaying = false;
		this.selectedIndex = PlaybackInfo.speeds.indexOf(PlaybackInfo.defaultSpeed);
		this.timerElapsedTimeProptn = 0;
	}
}

const dateFormatter = d3.timeFormat("%Y-%m-%d");
const tooltipDateFormatter = d3.timeFormat("%b %-d");
function getDateNDaysAfter(startDate: DateString, n: number): string {
	return dateFormatter(new Date(dateStrParser(startDate).getTime() + n * MS_PER_DAY));
}

function moveTooltipTo(x: number, y: number) {
	tooltip.style("top", `${+y - 30}px`).style("left", `${+x + 10}px`);
}

function getFormatter(caseType: CaseType, count: CountMethod, smoothAvgDays: number) {
	return (count === "dodd" && smoothAvgDays > 1) || isPerCapita(caseType)
		? numberFormatters.float
		: numberFormatters.int;
}

function getDataOnDate({
	feature,
	count,
	dateKey,
	caseType,
	smoothAvgDays,
}: {
	feature: Feature;
	count: CountMethod;
	dateKey: DateString;
	caseType: CaseType;
	smoothAvgDays?: number;
}): number | null {
	if (typeof feature.covidData === "undefined") {
		return null;
	}

	const data: DataGroup =
		count === "dodd" ? feature.covidData.dodd : feature.covidData.net;

	const index = feature.covidData.date[dateKey];
	if (typeof index === "undefined") {
		return null;
	}

	smoothAvgDays = smoothAvgDays as number;

	let value: number;
	if (count === "dodd" && smoothAvgDays >= 2) {
		let sum = 0;
		for (let i = index; i > index - smoothAvgDays; --i) {
			const x = data[caseType][i];
			sum += x;
		}

		value = sum / smoothAvgDays;
		if (isNaN(value)) {
			return null;
		}
	} else {
		value = data[caseType][index];
	}

	return value;
}

type TooltipVisibility = "visible" | "hidden" | "nochange";
function updateTooltip({ visibility }: { visibility: TooltipVisibility }) {
	const { feature, count, dateKey, caseType, smoothAvgDays } = tooltip.datum();

	if (typeof feature === "undefined") {
		return;
	}

	const dateStr = tooltipDateFormatter(dateStrParser(dateKey).getTime() - MS_PER_DAY);

	const location = feature.properties.name;

	const value = getDataOnDate({
		feature,
		count,
		dateKey,
		caseType,
		smoothAvgDays,
	});

	const formatter = getFormatter(caseType, count, smoothAvgDays);
	const countStr = value === null ? "~No data~" : formatter(value);

	tooltip.html(`${dateStr}<br>${location}<br>${countStr}`);
	if (visibility !== "nochange") {
		tooltip.style("visibility", visibility);
	}
}

let mouseMoved = false;
let hasPlayedAnimation = false;

let graphIsCurrentlyZooming = false;

type PrevChoroplethInfo = {
	location: WorldLocation;
	geoPath: any;
	zoom: any;
	dateStr: DateString;
};
let prevChoroplethInfo: PrevChoroplethInfo = ({
	location: null,
	geoPath: null,
	zoom: null,
	dateStr: null,
} as unknown) as PrevChoroplethInfo;

function updateMaps({
	choropleth,
	dateIndex,
	smoothAvgDays,
}: {
	choropleth: any;
	dateIndex?: number;
	smoothAvgDays?: number;
}) {
	const {
		count,
		location,
		allCovidData,
		allGeoData,
		playbackInfo,
	}: {
		count: CountMethod;
		location: WorldLocation;
		allCovidData: AllCovidData;
		allGeoData: AllGeoData;
		playbackInfo: PlaybackInfo;
	} = choropleth.datum();

	const scopedCovidData: ScopedCovidData = allCovidData[location];
	const scopedGeoData: ScopedGeoData = allGeoData[location];

	const didChangeLocation = location !== prevChoroplethInfo.location;

	let geoPath: any;
	const zoom = prevChoroplethInfo.zoom;
	if (!didChangeLocation) {
		geoPath = prevChoroplethInfo.geoPath;
	} else {
		const projectionExtent = [
			[0, 0],
			[
				plotAesthetics.mapWidth[location] - plotAesthetics.map.pad,
				plotAesthetics.mapHeight[location] - plotAesthetics.map.pad,
			],
		];

		const projection = (location === "usa"
			? d3.geoAlbersUsa()
			: d3.geoTimes()
		).fitExtent(projectionExtent, scopedGeoData);

		geoPath = d3.geoPath(projection);

		zoom.scaleExtent([1, plotAesthetics.map.maxZoom[location]]).translateExtent([
			[0, 0],
			[plotAesthetics.width[location], plotAesthetics.height[location]],
		]);

		prevChoroplethInfo.location = location;
		prevChoroplethInfo.geoPath = geoPath;
	}

	const legendTransX =
		plotAesthetics.mapWidth[location] + plotAesthetics.legend.padLeft;
	const legendTransY =
		(plotAesthetics.title.height +
			plotAesthetics.height[location] -
			plotAesthetics.legend.height[location]) /
		2;

	const { min_nonzero: minDate, max: maxDate } = scopedCovidData.agg.net.date;
	const firstDay = dateStrParser(minDate);
	const lastDay = dateStrParser(maxDate);
	const totalDaysElapsed = Math.round(
		(lastDay.getTime() - firstDay.getTime()) / MS_PER_DAY,
	);

	if (!didChangeLocation || prevChoroplethInfo.dateStr === null) {
		if (typeof dateIndex === "undefined" || dateIndex === null) {
			dateIndex = choropleth.selectAll(".date-slider").node().value;
		}
	} else {
		const prevDateStr = prevChoroplethInfo.dateStr;
		const prevDate = dateStrParser(prevDateStr);
		dateIndex = Math.round(prevDate.getTime() - firstDay.getTime()) / MS_PER_DAY;
	}
	dateIndex = dateIndex as number;
	if (dateIndex > totalDaysElapsed) {
		dateIndex = totalDaysElapsed;
	} else if (dateIndex < 0) {
		dateIndex = 0;
	}

	const dateKey = getDateNDaysAfter(minDate, dateIndex);
	prevChoroplethInfo.dateStr = dateKey;

	const { barWidth, height: barHeights } = plotAesthetics.legend;
	const barHeight = barHeights[location];
	choropleth
		.selectAll(".plot-container")
		.each(function (this: Node, { caseType }: { caseType: CaseType }) {
			const plotContainer = d3.select(this);
			const svg = plotContainer.selectAll("svg");
			if (didChangeLocation) {
				svg.attr("width", plotAesthetics.width[location]).attr(
					"height",
					plotAesthetics.height[location],
				);
			}

			const mainPlotArea = svg.selectAll("g.main-plot-area");

			const mapContainer = mainPlotArea
				.selectAll(".map-container")
				.data([
					{
						tx: plotAesthetics.map.originX,
						ty: plotAesthetics.map.originY,
					},
				])
				.join((enter: any) =>
					enter
						.append("g")
						.classed("map-container", true)
						.on("dblclick", function (this: Node) {
							const mc = d3.select(this);
							const t = plotAesthetics.map.zoomTransition;
							mc.transition(t).call(zoom.transform, d3.zoomIdentity);
							mc.selectAll(".state-boundary")
								.transition(t)
								.attr("stroke-width", plotAesthetics.map.borderWidth);
						})
						.attr(
							"transform",
							(d: { tx: number; ty: number }) =>
								`translate(${d.tx},${d.ty})`,
						),
				);

			// Dummy rectangle whose purpose is to catch zoom events that don't start inside a region boundary (e.g., a drag in the middle of the ocean)
			mapContainer
				.selectAll(".dummy-rect")
				.data([0])
				.join((enter: any) => enter.append("rect").classed("dummy-rect", true))
				.attr("x", 0)
				.attr("y", 0)
				.attr("width", plotAesthetics.mapWidth[location])
				.attr("height", plotAesthetics.mapHeight[location])
				.attr("fill-opacity", 0)
				.attr("stroke", "#ccc")
				.attr("stroke-width", 1);

			if (didChangeLocation) {
				mapContainer.call(zoom.transform, d3.zoomIdentity);

				mapContainer
					.selectAll(".map")
					.data([0])
					.join((enter: any) => enter.append("g").classed("map", true))
					.selectAll("path")
					.data(scopedGeoData.features)
					.join("path")
					.attr("d", geoPath)
					.attr("stroke", "#fff8")
					.attr("stroke-width", plotAesthetics.map.borderWidth);
				// I think this has to go after the map in order for it to catch zoom events (the zoom catcher has to have a greater z-index than the map itself). I'd have to check if this still *has* to go here but nothing is hurt by it going here, so it's not moving
				mapContainer.call(zoom);
			}

			const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[count][
				caseType
			];
			const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);

			// console.log(map);
			mapContainer
				.selectAll(".map")
				.selectAll("path")
				.attr("fill", (feature: Feature) => {
					const value = getDataOnDate({
						feature,
						count,
						dateKey,
						caseType,
						smoothAvgDays,
					});

					if (value === 0) {
						return plotAesthetics.colors.zero;
					}

					if (value === null || value < vmin) {
						return `url(#missingDataFillPattern)`; //plotAesthetics.colors.missing;
					}

					return plotAesthetics.colors.scale(colorScale(value));
				})
				.classed("state-boundary", true)
				.on("mouseover", (d: Feature) => {
					tooltip.datum({
						...tooltip.datum(),
						feature: d,
						caseType,
						count,
						smoothAvgDays,
					});
					updateTooltip({ visibility: "visible" });
				})
				.on("mousemove", () => {
					if (!mouseMoved) {
						const dateIndex = +dateSliderNode.value;
						tooltip.datum({
							...tooltip.datum(),
							dateKey: getDateNDaysAfter(minDate, dateIndex),
							smoothAvgDays,
						});
						updateTooltip({ visibility: "visible" });
					}

					mouseMoved = true;

					tooltip.style("visibility", "visible");
					moveTooltipTo(d3.event.pageX, d3.event.pageY);
				})
				.on("mouseout", () => {
					tooltip.style("visibility", "hidden");
					mouseMoved = false;
				});

			const legend = svg
				.selectAll(".legend")
				.attr("transform", `translate(${legendTransX} ${legendTransY})`);

			legend
				.selectAll(".gradient")
				.attr("width", barWidth)
				.attr("height", barHeight);

			const legendScale = d3
				.scaleLog()
				.nice()
				.base(10)
				.domain([vmin, vmax])
				.range([barHeight, 0]);

			const nLegendTicks = 7;
			legend
				.selectAll(".legend-tick")
				.data(legendScale.ticks(nLegendTicks).map(legendScale))
				.join(
					(enter: any) => enter.append("line").classed("legend-tick", true),
					(update: any) => update,
					(exit: any) => exit.remove(),
				)
				.attr("x1", (barWidth * 2) / 3)
				.attr("x2", barWidth)
				.attr("y1", (ys: number) => ys)
				.attr("y2", (ys: number) => ys)
				.attr("stroke", "white")
				.attr("stroke-width", 1);

			const bigNumberTickFormatter = legendScale.tickFormat(
				nLegendTicks,
				isPerCapita(caseType) ? "~g" : "~s",
			);
			const smallNumberTickFormatter = legendScale.tickFormat(
				nLegendTicks,
				count === "net" ? "~g" : "~r",
			);
			legend
				.selectAll(".legend-number")
				.data(legendScale.ticks(nLegendTicks), (_: any, i: number) => i)
				.join(
					(enter: any) =>
						enter
							.append("text")
							.classed("legend-number", true)
							.attr("x", barWidth + 4)
							.attr("fill", "black")
							.attr("font-size", 12)
							.attr("text-anchor", "left")
							.attr("alignment-baseline", "middle"),
					(update: any) => update,
					(exit: any) => exit.remove(),
				)
				.attr("y", (y: number) => legendScale(y))
				.text((y: number) => {
					const formatter =
						y < 1 ? smallNumberTickFormatter : bigNumberTickFormatter;
					return `${formatter(y)}`;
				});

			// Add title
			const titlePrefixStr = count === "dodd" ? "Increase in" : "Total";
			let caseTypeStr: string = caseType;
			let titleSuffixStr = "";
			if (isPerCapita(caseType)) {
				caseTypeStr = caseTypeStr.replace("_per_capita", "");
				titleSuffixStr = " Per 100,000 People";
			}
			caseTypeStr = caseTypeStr.replace(/^./, (c: string) => c.toUpperCase());

			const titleStr = `${titlePrefixStr} ${caseTypeStr}${titleSuffixStr}`;
			svg.selectAll(".title").text(titleStr);

			// Finally, configure the date sliders
			plotContainer.selectAll(".date-slider").each(function (this: any) {
				this.min = 0;
				this.max = totalDaysElapsed;
				this.step = 1;
			});
		});

	const dateSliderNode = choropleth
		.selectAll(".date-slider")
		.property("value", dateIndex)
		.node();
	const movingAvgSliders = choropleth.selectAll(".smooth-avg-slider");

	console.log(smoothAvgDays);
	// If non-null, apply this slider's moving avg to all other sliders
	if (
		count === "dodd" &&
		(typeof smoothAvgDays === "undefined" || smoothAvgDays === null)
	) {
		smoothAvgDays = choropleth.selectAll(".smooth-avg-slider").node().value;
	} else if (typeof smoothAvgDays !== "undefined") {
		smoothAvgDays = +smoothAvgDays;
	}
	smoothAvgDays = smoothAvgDays as number;
	movingAvgSliders.property("value", smoothAvgDays);

	const movingAvgRows = choropleth.selectAll(".moving-avg-row");
	if (count === "dodd") {
		movingAvgRows.style("visibility", "visible");
	} else {
		movingAvgRows.style("visibility", "hidden");
	}

	const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
	const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
	choropleth.selectAll(".date-span").text(dateStr);

	choropleth
		.selectAll(".smooth-avg-text")
		.text(`Moving avg: ${smoothAvgDays} day${smoothAvgDays > 1 ? "s" : ""}`);

	if (hasPlayedAnimation && !playbackInfo.isPlaying) {
		choropleth
			.selectAll(".play-button")
			.text(dateIndex === +dateSliderNode.max ? "Restart" : "Play");
	}

	Object.assign(tooltip.datum(), { dateKey, smoothAvgDays });
	updateTooltip({ visibility: "nochange" });
}

const numberFormatters = { int: d3.format(",~r"), float: d3.format(",.2f") };

const tooltip: {
	datum: (d?: {
		feature?: Feature;
		count?: CountMethod;
		dateKey?: DateString;
		caseType?: CaseType;
		smoothAvgDays?: number;
	}) => {
		feature: Feature;
		count: CountMethod;
		dateKey: DateString;
		caseType: CaseType;
		smoothAvgDays: number;
	};
	style: any;
	attr: any;
	html: any;
} = d3
	.select("body")
	.selectAll()
	.data([{ dateKey: null, location: null, countStr: null }])
	.join("div")
	.attr("id", "map-tooltip");

function _initializeChoropleth({
	allCovidData,
	allGeoData,
}: {
	allCovidData: AllCovidData;
	allGeoData: AllGeoData;
}) {
	const datum: {
		playbackInfo: PlaybackInfo;
		location: WorldLocation;
		count: CountMethod;
		allCovidData: AllCovidData;
		allGeoData: AllGeoData;
	} = {
		playbackInfo: new PlaybackInfo(),
		location: "usa",
		count: "dodd",
		allCovidData,
		allGeoData,
	};
	const choropleth = d3.select("#map-plots").selectAll().data([datum]).join("div");

	const checkboxGroup = choropleth.append("div").classed("checkbox-table", true);
	const checkboxTable = checkboxGroup.append("table");
	checkboxTable
		.append("tr")
		.selectAll()
		.data(["Location", "Count"])
		.join("th")
		.text((d: string) => d)
		.attr("colspan", 2);
	const rows: { key: "location" | "count"; value: string; name: string }[][] = [
		[
			{ key: "location", value: "usa", name: "USA" },
			{ key: "count", value: "dodd", name: "Daily Increase" },
		],
		[
			{ key: "location", value: "world", name: "World" },
			{ key: "count", value: "net", name: "Total Cases" },
		],
	];
	for (const row of rows) {
		const tr = checkboxTable.append("tr");
		for (const col of row) {
			const { key, value, name } = col;
			tr.append("td").text(name);
			tr.append("td")
				.append("input")
				.property("checked", value === datum[key])
				.attr("type", "radio")
				.property("name", key)
				.on("change", function (d: any) {
					choropleth.datum()[key] = value;
					updateMaps({ choropleth });
				});
		}
	}

	const plotContainers = choropleth
		.selectAll()
		.data(
			([
				"cases",
				"cases_per_capita",
				"deaths",
				"deaths_per_capita",
			] as CaseType[]).map(caseType => ({ caseType })),
		)
		.join("div")
		.classed("plot-container", true);

	const svg = plotContainers.append("svg").classed("plot", true);
	const legend = svg.append("g").classed("legend", true);
	legend
		.append("rect")
		.classed("gradient", true)
		.attr("x", 0)
		.attr("y", 0)
		.attr("fill", `url(#${plotAesthetics.legend.gradientID})`);
	svg.append("text")
		.classed("title", true)
		.attr("x", 20)
		.attr("y", plotAesthetics.title.height)
		.attr("text-anchor", "left")
		.attr("alignment-baseline", "top")
		.attr("font-size", 24)
		.attr("font-family", "sans-serif")
		.attr("fill", "black");

	const zoom = d3
		.zoom()
		.filter(function () {
			return (
				d3.event.type !== "dblclick" &&
				(d3.event.type !== "wheel" || d3.event.shiftKey) &&
				(!d3.event.touches || d3.event.touches.length === 2)
			);
		})
		.on("zoom", function (this: Node) {
			tooltip.style("visibility", "hidden");
			const transform = d3.event.transform;

			d3.select(this).selectAll(".map").attr("transform", transform);

			const mapContainer = this;
			// Apply zoom to other map containers in plotGroup, making sure not to let them try to zoom this map container again! (else an infinite loop will occur)
			if (!graphIsCurrentlyZooming) {
				// Holy race condition Batman (each and zoom are synchronous so it's fine)
				graphIsCurrentlyZooming = true;
				choropleth.selectAll(".map-container").each(function (this: Node) {
					if (this !== mapContainer) {
						zoom.transform(d3.select(this), transform);
					}
				});
				graphIsCurrentlyZooming = false;
			}

			// Rescale state boundary thickness to counter zoom
			choropleth
				.selectAll(".state-boundary")
				.attr("stroke-width", plotAesthetics.map.borderWidth / transform.k);
		});
	prevChoroplethInfo.zoom = zoom;

	// Create defs: gradient (for legend) and clipPath (for clipping map to rect bounds when zooming in)
	const location = WORLD_LOCATIONS[0];
	const count = COUNT_METHODS[0];

	const defs = svg.append("defs");
	// https://stackoverflow.com/a/14500054/5496433
	defs.append("pattern")
		.attr("id", "missingDataFillPattern")
		.attr("patternUnits", "userSpaceOnUse")
		.attr("width", 8)
		.attr("height", 8)
		.append("path")
		.attr("d", "M-2,2 l3,-3 M0,8 l8,-8 M6,10 l3,-3")
		.style("stroke", plotAesthetics.colors.missing)
		.style("stroke-width", 2);
	const verticalLegendGradient = defs
		.append("linearGradient")
		.attr("id", plotAesthetics.legend.gradientID)
		.attr("x1", "0%")
		.attr("x2", "0%")
		.attr("y1", "100%")
		.attr("y2", "0%");
	d3.range(plotAesthetics.colors.nSteps).forEach((i: number) => {
		const percent = (100 * i) / (plotAesthetics.colors.nSteps - 1);
		const proptn = percent / 100;

		verticalLegendGradient
			.append("stop")
			.attr("offset", `${percent}%`)
			.attr("stop-color", plotAesthetics.colors.scale(proptn))
			.attr("stop-opacity", 1);
	});

	const mainPlotAreas = svg.append("g").classed("main-plot-area", true);
	const clipPathID = `plot-clip-${location}-${count}`;
	defs.append("clipPath")
		.attr("id", clipPathID)
		.append("rect")
		.attr("x", plotAesthetics.map.originX)
		.attr("y", plotAesthetics.map.originY)
		.attr("width", plotAesthetics.mapWidth[location])
		.attr("height", plotAesthetics.mapHeight[location]);
	mainPlotAreas.attr("clip-path", `url(#${clipPathID})`);

	const { playbackInfo }: { playbackInfo: PlaybackInfo } = datum;

	// Create buttons, sliders, everything UI related not dealing with the SVGs themselves
	const dateSliderRows = plotContainers
		.append("div")
		.classed("input-row", true)
		.append("span");
	dateSliderRows
		.append("span")
		.classed("date-span", true)
		.classed("slider-text", true);
	const dateSliders = dateSliderRows
		.selectAll()
		.data(() => [{ choropleth }])
		.join("input")
		.classed("date-slider", true)
		.classed("input-slider", true)
		.attr("type", "range")
		// Temporary values, used to place the slider's knob to the right while we await the actual data we'll use to compute its range
		.attr("min", 0)
		.attr("max", 1)
		.property("value", 1)
		.on("input", function (this: any, d: PlotInfo) {
			const dateIndex = +this.value;
			updateMaps({ choropleth, dateIndex });
		});
	const dateSliderNode = dateSliders.node();

	const smoothAvgSliderRows = plotContainers
		.append("div")
		.classed("input-row", true)
		.classed("moving-avg-row", true)
		.append("span");
	smoothAvgSliderRows
		.append("span")
		.classed("smooth-avg-text", true)
		.classed("slider-text", true);
	smoothAvgSliderRows
		.selectAll()
		.data(() => [{ choropleth }])
		.join("input")
		.classed("smooth-avg-slider", true)
		.classed("input-slider", true)
		.attr("type", "range")
		.attr("min", 1)
		.attr("max", 7)
		.property("value", 1)
		.on("input", function (this: any, d: PlotInfo) {
			const smoothAvgDays = +this.value;
			updateMaps({ choropleth, smoothAvgDays });
		});

	const buttonsRows = plotContainers
		.append("div")
		.classed("button-row", true)
		.append("span")
		.classed("button-container", true);

	const buttonSpans = buttonsRows.append("span").classed("speed-buttons-span", true);

	const playButtons = buttonSpans
		.selectAll()
		.data(() => [playbackInfo])
		.join("button")
		.classed("play-button", true)
		.text("Play");

	function haltPlayback(playbackInfo: PlaybackInfo) {
		playbackInfo.isPlaying = false;
		clearInterval(playbackInfo.timer);
		const now = new Date();
		const elapsedTimeMS =
			now.getTime() - (playbackInfo.timerStartDate as Date).getTime();
		(playbackInfo.timerElapsedTimeProptn as number) +=
			elapsedTimeMS / playbackInfo.currentIntervalMS;
	}

	function startPlayback(playbackInfo: PlaybackInfo) {
		playbackInfo.isPlaying = true;

		const maxDateIndex = parseFloat(dateSliderNode.max);
		console.log(maxDateIndex);

		if (dateSliderNode.value === dateSliderNode.max) {
			updateMaps({ choropleth, dateIndex: 0 });
			// A number indistinguishable from 0 to a human, but not to a computer
			playbackInfo.timerElapsedTimeProptn = 0.0000001;
		}

		function updateDate() {
			playbackInfo.timerStartDate = new Date();
			playbackInfo.timerElapsedTimeProptn = 0;

			const dateIndex = parseFloat(dateSliderNode.value);
			if (dateIndex < maxDateIndex) {
				updateMaps({
					choropleth,
					dateIndex: dateIndex + 1,
				});
			}

			// If it's the last date, end the timer (don't wait for the date to be one past the end; just end it when it hits the end)
			if (dateIndex >= maxDateIndex - 1) {
				clearInterval(playbackInfo.timer);
				playbackInfo.isPlaying = false;
				playButtons.text("Restart");
			}
		}

		playbackInfo.timerStartDate = new Date();
		const timeRemainingProptn = 1 - playbackInfo.timerElapsedTimeProptn;

		const initialIntervalMS =
			timeRemainingProptn === 1
				? 0
				: timeRemainingProptn * playbackInfo.currentIntervalMS;

		playbackInfo.timer = setTimeout(() => {
			updateDate();
			playbackInfo.timer = setInterval(
				updateDate,
				playbackInfo.currentIntervalMS,
			);
		}, initialIntervalMS);
	}

	playButtons.on("click", function (playbackInfo: PlaybackInfo) {
		if (playbackInfo.isPlaying) {
			haltPlayback(playbackInfo);
			playButtons.text("Play");
		} else {
			hasPlayedAnimation = true;
			startPlayback(playbackInfo);
			playButtons.text("Pause");
		}
	});

	const speedButtons = buttonSpans
		.selectAll()
		.data(() =>
			PlaybackInfo.speeds.map(speed => {
				return { speed, playbackInfo };
			}),
		)
		.join("button")
		.classed("speed-button", true)
		.text(({ speed }: { speed: number }) => `${speed}x`)
		.property(
			"disabled",
			({ speed }: { speed: number }) => speed === PlaybackInfo.defaultSpeed,
		);

	speedButtons.on("click", function (
		{
			speed,
			playbackInfo,
		}: {
			speed: number;
			playbackInfo: PlaybackInfo;
		},
		i: number,
	) {
		const wasPlaying = playbackInfo.isPlaying;
		// Order matters here; calculations in haltPlayback require the old value of selectedIndex
		if (wasPlaying) {
			haltPlayback(playbackInfo);
		}
		playbackInfo.selectedIndex = i;
		speedButtons.each(function (this: Node, d: any) {
			d3.select(this).property("disabled", d.speed === speed);
		});
		if (wasPlaying) {
			startPlayback(playbackInfo);
		}
	});

	updateMaps({
		choropleth,
		dateIndex: Infinity,
		smoothAvgDays: 5,
	});
}

export function initializeChoropleths(
	allCovidData: AllCovidData,
	allGeoData: AllGeoData,
) {
	_initializeChoropleth({
		allCovidData,
		allGeoData,
	});
}
