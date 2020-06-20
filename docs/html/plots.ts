declare const d3: any;

type DateString = string;
type CaseType = "cases" | "cases_per_capita" | "deaths" | "deaths_per_capita";
type WorldLocation = "usa" | "world";
type CountMethod = "net" | "dodd";
interface Scope {
	location: WorldLocation;
	count: CountMethod;
}
// type Scope = { location: "usa"; count: "net" } | { location: "world"; count: "net" };
type ScopeLocation = string;

const WORLD_LOCATIONS: WorldLocation[] = ["usa", "world"];
const COUNT_METHODS: CountMethod[] = ["dodd", "net"];
const SCOPES: Scope[] = (() => {
	const scopes: Scope[] = [];
	COUNT_METHODS.forEach((count: CountMethod) => {
		WORLD_LOCATIONS.forEach((location: WorldLocation) => {
			scopes.push({ location, count });
		});
	});
	return scopes;
})();

interface AllGeoData {
	usa: ScopedGeoData;
	world: ScopedGeoData;
}

interface ScopedGeoData {
	type: string;
	features: Feature[];
}

interface Feature {
	properties: {
		code: string;
		name: string;
	};
	covidData: LocationCovidData;
}

// usa/world -> "data" -> state/country -> date -> data
interface AllCovidData {
	usa: ScopedCovidData;
	world: ScopedCovidData;
}

interface Aggregated<T> {
	min: T;
	min_nonzero: T;
	max: T;
}

type AggNumber = Aggregated<number>;
type AggDate = Aggregated<DateString>;

interface ScopedCovidData {
	agg: {
		[key: string]: {
			cases: AggNumber;
			cases_per_capita: AggNumber;
			deaths: AggNumber;
			deaths_per_capita: AggNumber;
			date: AggDate;
		};
	};
	data: {
		[key: string]: LocationCovidData;
	};
}

interface DataGroup {
	cases: number[];
	cases_per_capita: number[];
	deaths: number[];
	deaths_per_capita: number[];
}

interface LocationCovidData extends DataGroup {
	date: { [key: string]: number };
	day_over_day_diffs: DataGroup;
}

interface PlotInfo {
	location: WorldLocation;
	count: CountMethod;
	caseType: CaseType;
	scopedCovidData?: ScopedCovidData;
	plotGroup?: any;
}

const MS_PER_DAY = 86400 * 1000;

const plotAesthetics = Object.freeze(
	(() => {
		const pa = {
			width: { usa: 500, world: 500 },
			height: { usa: 325, world: 300 },
			colors: {
				scale: (t: number) => d3.interpolateCividis(1 - t),
				nSteps: 101,
				missing: "#ccc",
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

			mapWidth: null,
			mapHeight: null,
		};

		pa.map.originX = pa.map.pad;
		pa.map.originY = pa.title.height + pa.map.pad;

		pa.mapWidth = {};
		Object.keys(pa.width).forEach((scope: ScopeLocation) => {
			pa.mapWidth[scope] =
				pa.width[scope] -
				pa.map.originX -
				(pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight) -
				pa.map.pad;
		});

		pa.mapHeight = {};
		Object.keys(pa.height).forEach((scope: ScopeLocation) => {
			pa.mapHeight[scope] = pa.height[scope] - pa.map.originY - pa.map.pad;
		});
		return pa;
	})(),
);

function isPerCapita(caseType: CaseType) {
	return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}

const dateStrParser = d3.timeParse("%Y-%m-%d");
const dateFormatter = d3.timeFormat("%Y-%m-%d");
const tooltipDateFormatter = d3.timeFormat("%b %-d");
function getDateNDaysAfter(startDate: DateString, n: number): string {
	return dateFormatter(new Date(dateStrParser(startDate).getTime() + n * MS_PER_DAY));
}

function assignData({
	allCovidData,
	allGeoData,
}: {
	allCovidData: AllCovidData;
	allGeoData: AllGeoData;
}) {
	WORLD_LOCATIONS.forEach(location => {
		const scopedGeoData: ScopedGeoData = allGeoData[location];
		scopedGeoData.features.forEach(feature => {
			const covidData: LocationCovidData =
				allCovidData[location].data[feature.properties.code];
			feature.covidData = covidData;

			if (typeof covidData === "undefined") {
				return;
			}

			feature.covidData.day_over_day_diffs = (() => {
				const dodd = {
					cases: [],
					cases_per_capita: [],
					deaths: [],
					deaths_per_capita: [],
				};

				for (let [caseType, data] of Object.entries(dodd)) {
					for (let i = 0; i < Object.keys(covidData.date).length; ++i) {
						const diff =
							covidData[caseType][i] - covidData[caseType][i - 1];
						if (!diff) {
							data.push(0);
						} else {
							data.push(diff);
						}
					}
				}

				return dodd;
			})();
		});
	});
}

const mouseActions: {
	mouseover: (d: Feature) => void;
	mousemove: () => void;
	mouseout: () => void;
	info: { prevFeature: any };
} = {
	mouseover: null,
	mousemove: null,
	mouseout: null,
	info: { prevFeature: null },
};

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
	smoothAvgDays: number;
}): number {
	if (typeof feature.covidData === "undefined") {
		return null;
	}

	const data: DataGroup =
		count === "dodd" ? feature.covidData.day_over_day_diffs : feature.covidData;

	const index = feature.covidData.date[dateKey];
	if (typeof index === "undefined") {
		return null;
	}

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

function updateMaps({
	plotGroup,
	dateIndex,
	smoothAvgDays,
}: {
	plotGroup: any;
	dateIndex: number;
	smoothAvgDays: number;
}) {
	const {
		count,
		scopedCovidData,
		playbackInfo,
	}: {
		count: CountMethod;
		scopedCovidData: ScopedCovidData;
		playbackInfo: PlaybackInfo;
	} = plotGroup.datum();

	if (typeof dateIndex === "undefined" || dateIndex === null) {
		dateIndex = plotGroup.selectAll(".date-slider").node().value;
	}

	if (
		count === "dodd" &&
		(typeof smoothAvgDays === "undefined" || smoothAvgDays === null)
	) {
		smoothAvgDays = plotGroup.selectAll(".smooth-avg-slider").node().value;
	}
	smoothAvgDays = +smoothAvgDays;

	const dateSliderNode = plotGroup
		.selectAll(".date-slider")
		.property("value", dateIndex)
		.node();

	const smoothAvgSliderNode = plotGroup
		.selectAll(".smooth-avg-slider")
		.property("value", smoothAvgDays)
		.node();

	const minDate = scopedCovidData.agg.net.date.min_nonzero;
	const dateKey = getDateNDaysAfter(minDate, dateIndex);

	const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
	const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
	plotGroup.selectAll(".date-span").text(dateStr);

	plotGroup
		.selectAll(".smooth-avg-text")
		.text(`Moving avg: ${smoothAvgDays} day${smoothAvgDays > 1 ? "s" : ""}`);

	if (!playbackInfo.isPlaying) {
		plotGroup.selectAll(".play-button").text("Play");
	}

	tooltip.datum({ ...tooltip.datum(), dateKey, smoothAvgDays });
	updateTooltip({ visibility: "nochange" });

	plotGroup
		.selectAll(".plot-container")
		.each(function ({ caseType }: { caseType: CaseType }) {
			const plotContainer = d3.select(this);

			const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[count][
				caseType
			];
			const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);

			const svg = plotContainer.selectAll("svg").selectAll(".map");

			mouseActions.mouseover = (d: Feature) => {
				tooltip.datum({
					...tooltip.datum(),
					feature: d,
					caseType,
					count,
					smoothAvgDays,
				});
				updateTooltip({ visibility: "visible" });
			};
			mouseActions.mousemove = () => {
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
			};
			mouseActions.mouseout = () => {
				tooltip.style("visibility", "hidden");
				mouseMoved = false;
			};

			const p = svg
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
						return plotAesthetics.colors.missing;
					}

					return plotAesthetics.colors.scale(colorScale(value));
				})
				.classed("state-boundary", true);

			Object.entries(mouseActions).forEach(([event, action]) => [
				p.on(event, action),
			]);
		});
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

let graphHasBegunZooming = false;
function initializeChoropleth({
	plotGroup,
	allCovidData,
	allGeoData,
}: {
	plotGroup: any;
	allCovidData: AllCovidData;
	allGeoData: AllGeoData;
}) {
	const { location, count } = plotGroup.datum();
	const scopedCovidData: ScopedCovidData = allCovidData[location];
	const scopedGeoData: ScopedGeoData = allGeoData[location];

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

	const path = d3.geoPath(projection);

	const zoom = d3
		.zoom()
		.scaleExtent([1, plotAesthetics.map.maxZoom[location]])
		.translateExtent([
			[0, 0],
			[plotAesthetics.width[location], plotAesthetics.height[location]],
		])
		.filter(function () {
			return (
				d3.event.type !== "dblclick" &&
				(d3.event.type !== "wheel" || d3.event.shiftKey) &&
				(!d3.event.touches || d3.event.touches.length === 2)
			);
		})
		.on("zoom", function () {
			tooltip.style("visibility", "hidden");
			const transform = d3.event.transform;

			d3.select(this).selectAll(".map").attr("transform", transform);

			const mapContainer = this;
			// Apply zoom to other map containers in plotGroup, making sure not to let them try to zoom this map container again! (else an infinite loop will occur)
			if (!graphHasBegunZooming) {
				// Holy race condition Batman (each and zoom are synchronous so it's fine)
				graphHasBegunZooming = true;
				plotGroup
					.selectAll(".map-container")
					.filter(function () {
						return this !== mapContainer;
					})
					.each(function () {
						zoom.transform(d3.select(this), transform);
					});
				graphHasBegunZooming = false;
			}

			plotGroup
				.selectAll(".state-boundary")
				.attr("stroke-width", plotAesthetics.map.borderWidth / transform.k);
		});

	let idleTimeout: number = null;
	const idleDelay = 350;
	const idled = () => {
		idleTimeout = null;
	};

	plotGroup.datum({ ...plotGroup.datum(), scopedCovidData });

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
	const daysElapsed = Math.round((lastDay - firstDay) / MS_PER_DAY);

	plotGroup.selectAll(".plot-container").each(function () {
		const plotContainer = d3.select(this);
		const caseType = plotContainer.datum().caseType;
		const svg = plotContainer.selectAll("svg");
		const mainPlotArea = svg.selectAll("g.main-plot-area");

		const mapContainer = mainPlotArea
			.selectAll()
			.data([
				{
					tx: plotAesthetics.map.originX,
					ty: plotAesthetics.map.originY,
				},
			])
			.join("g")
			.classed("map-container", true)
			.attr(
				"transform",
				(d: { tx: number; ty: number }) => `translate(${d.tx},${d.ty})`,
			);

		// Dummy rectangle whose purpose is to catch zoom events that don't start inside a region boundary (e.g., a drag in the middle of the ocean)
		mapContainer
			.append("rect")
			.attr("x", 0)
			.attr("y", 0)
			.attr("width", plotAesthetics.mapWidth[location])
			.attr("height", plotAesthetics.mapHeight[location])
			.attr("fill-opacity", 0)
			.attr("stroke", "#ccc")
			.attr("stroke-width", 1);

		mapContainer.on("dblclick", function () {
			const mc = d3.select(this);
			const t = plotAesthetics.map.zoomTransition;
			mc.transition(t).call(zoom.transform, d3.zoomIdentity);
			// maps.transition(t).attr("transform", "scaleX(1)");
			mc.selectAll(".state-boundary")
				.transition(t)
				.attr("stroke-width", plotAesthetics.map.borderWidth);
		});

		const map = mapContainer
			.append("g")
			.classed("map", true)
			.attr("transform", "translate(0 0)"); // A dummy transform just so it exists

		map.selectAll("path")
			.data(scopedGeoData.features)
			.join("path")
			.attr("d", path)
			.attr("stroke", "#fff8")
			.attr("stroke-width", plotAesthetics.map.borderWidth)
			.attr("pointer-events", "all");

		mapContainer.call(zoom);

		const legend = svg
			.append("g")
			.attr("transform", `translate(${legendTransX} ${legendTransY})`);

		const { barWidth, height: barHeights } = plotAesthetics.legend;
		const barHeight = barHeights[location];
		legend
			.append("rect")
			.attr("x", 0)
			.attr("y", 0)
			.attr("width", barWidth)
			.attr("height", barHeight)
			.attr("fill", `url(#${plotAesthetics.legend.gradientID})`);

		const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[count][caseType];
		const legendScale = d3
			.scaleLog()
			.nice()
			.base(10)
			.domain([vmin, vmax])
			.range([barHeight, 0]);

		legendScale.ticks(7).forEach((y: number) => {
			const ys = legendScale(y);
			legend
				.append("line")
				.attr("x1", (barWidth * 2) / 3)
				.attr("x2", barWidth)
				.attr("y1", ys)
				.attr("y2", ys)
				.attr("stroke", "white")
				.attr("stroke-width", 1);
		});

		const bigNumberTickFormatter = legendScale.tickFormat(
			7,
			isPerCapita(caseType) ? "~g" : "~s",
		);
		const smallNumberTickFormatter = legendScale.tickFormat(
			7,
			count === "net" ? "~g" : "~r",
		);
		legendScale.ticks(7).forEach((y: number) => {
			const formatter = y < 1 ? smallNumberTickFormatter : bigNumberTickFormatter;
			legend
				.append("text")
				.attr("x", barWidth + 4)
				.attr("y", legendScale(y))
				.text(`${formatter(y)}`)
				.attr("fill", "black")
				.attr("font-size", 12)
				.attr("font-family", "sans-serif")
				.attr("text-anchor", "left")
				.attr("alignment-baseline", "middle");
		});

		const prefixStr = count === "dodd" ? "New Daily" : "Total";
		let caseTypeStr = caseType;
		let suffixStr = "";
		if (isPerCapita(caseTypeStr)) {
			caseTypeStr = caseTypeStr.replace("_per_capita", "");
			suffixStr = " Per 100,000 People";
		}
		caseTypeStr = caseTypeStr.replace(/^./, (c: string) => c.toUpperCase());

		const titleStr = `${prefixStr} ${caseTypeStr}${suffixStr}`;
		svg.append("text")
			.attr("x", 20)
			.attr("y", plotAesthetics.title.height)
			.attr("text-anchor", "left")
			.attr("alignment-baseline", "top")
			.text(titleStr)
			.attr("font-size", 24)
			.attr("font-family", "sans-serif")
			.attr("fill", "black");

		plotContainer.selectAll(".date-slider").each(function () {
			this.min = 0;
			this.max = daysElapsed;
			this.step = 1;
		});
	});

	updateMaps({ plotGroup, dateIndex: daysElapsed, smoothAvgDays: null });
}

const plotGroups = d3
	.select("#map-plots")
	.selectAll()
	.data(
		SCOPES.map(scope => {
			return scope;
		}),
	)
	.join("div")
	.classed("plot-scope-group", true);

const plotContainers = plotGroups
	.selectAll()
	.data(function (scope: Scope) {
		return ["cases", "cases_per_capita", "deaths", "deaths_per_capita"].map(
			(caseType: CaseType) => ({
				...scope,
				caseType,
				plotGroup: d3.select(this),
			}),
		);
	})
	.join("div")
	.classed("plot-container", true);

const svgs = plotContainers
	.append("svg")
	.classed("plot", true)
	.attr("width", (d: PlotInfo) => plotAesthetics.width[d.location])
	.attr("height", (d: PlotInfo) => plotAesthetics.height[d.location]);

class PlaybackInfo {
	static speeds = [0.25, 0.5, 1, 2, 4];
	static defaultSpeed = 1;

	timer: number;
	isPlaying: Boolean;
	selectedIndex: number;
	timerStartDate: Date;
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
	}
}
// Create buttons, sliders, everything UI related not dealing with the SVGs themselves
(() => {
	plotGroups.each(function ({ count }: { count: CountMethod }) {
		const plotGroup = d3.select(this);
		const plotContainers = plotGroup.selectAll(".plot-container");
		const dateSliderRows = plotContainers
			.append("div")
			.classed("input-row", true)
			.append("span");
		dateSliderRows
			.append("span")
			.classed("date-span", true)
			.classed("slider-text", true);
		dateSliderRows
			.selectAll()
			.data(() => [{ plotGroup }])
			.join("input")
			.classed("date-slider", true)
			.classed("input-slider", true)
			.attr("type", "range")
			// Temporary values, used to place the slider's knob to the right while we await the actual data we'll use to compute its range
			.attr("min", 0)
			.attr("max", 1)
			.property("value", 1)
			.on("input", function (d: PlotInfo) {
				const dateIndex = +this.value;
				updateMaps({ plotGroup: d.plotGroup, dateIndex, smoothAvgDays: null });
			});

		if (count === "dodd") {
			const smoothAvgSliderRows = plotContainers
				.append("div")
				.classed("input-row", true)
				.append("span");
			smoothAvgSliderRows
				.append("span")
				.classed("smooth-avg-text", true)
				.classed("slider-text", true);
			smoothAvgSliderRows
				.selectAll()
				.data(() => [{ plotGroup }])
				.join("input")
				.classed("smooth-avg-slider", true)
				.classed("input-slider", true)
				.attr("type", "range")
				.attr("min", 1)
				.attr("max", 7)
				.property("value", 1)
				.on("input", function (d: PlotInfo) {
					const smoothAvgDays = +this.value;
					updateMaps({
						plotGroup: d.plotGroup,
						dateIndex: null,
						smoothAvgDays,
					});
				});
		}

		const playbackInfo = new PlaybackInfo();
		plotGroup.datum({ ...plotGroup.datum(), playbackInfo });

		const buttonsRows = plotGroup
			.selectAll(".plot-container")
			.append("div")
			.classed("button-row", true)
			.append("span")
			.classed("button-container", true);

		const buttonSpans = buttonsRows
			.append("span")
			.classed("speed-buttons-span", true);

		const playButtons = buttonSpans
			.selectAll()
			.data(() => [playbackInfo])
			.join("button")
			.classed("play-button", true)
			.text("Play");

		const dateSliders = plotGroup.selectAll(".date-slider");
		const dateSliderNode = dateSliders.node();

		function haltPlayback(playbackInfo: PlaybackInfo) {
			playbackInfo.isPlaying = false;
			clearInterval(playbackInfo.timer);
			const now = new Date();
			const elapsedTimeMS = now.getTime() - playbackInfo.timerStartDate.getTime();
			playbackInfo.timerElapsedTimeProptn +=
				elapsedTimeMS / playbackInfo.currentIntervalMS;
		}

		function startPlayback(playbackInfo: PlaybackInfo) {
			playbackInfo.isPlaying = true;

			const maxDateIndex = parseFloat(dateSliderNode.max);

			if (dateSliderNode.value === dateSliderNode.max) {
				updateMaps({ plotGroup, dateIndex: 0, smoothAvgDays: null });
				// A number indistinguishable from 0 (except to a computer)
				playbackInfo.timerElapsedTimeProptn = 0.0000001;
			}

			function updateDate() {
				playbackInfo.timerStartDate = new Date();
				playbackInfo.timerElapsedTimeProptn = 0;

				const dateIndex = parseFloat(dateSliderNode.value);
				if (dateIndex < maxDateIndex) {
					updateMaps({
						plotGroup,
						dateIndex: dateIndex + 1,
						smoothAvgDays: null,
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
			speedButtons.each(function (d: any) {
				d3.select(this).property("disabled", d.speed === speed);
			});
			if (wasPlaying) {
				startPlayback(playbackInfo);
			}
		});
	});
})();

// Create defs: gradient and clipPath
(() => {
	plotGroups.each(function (scope: Scope) {
		const svgs = d3.select(this).selectAll("svg");
		const defs = svgs.append("defs");
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

		const canvases = svgs.append("g").classed("main-plot-area", true);
		const clipPathID = `plot-clip-${scope.location}-${scope.count}`;
		defs.append("clipPath")
			.attr("id", clipPathID)
			.append("rect")
			.attr("x", plotAesthetics.map.originX)
			.attr("y", plotAesthetics.map.originY)
			.attr("width", plotAesthetics.mapWidth[scope.location])
			.attr("height", plotAesthetics.mapHeight[scope.location]);
		canvases.attr("clip-path", `url(#${clipPathID})`);
	});
})();

const nowMS = new Date().getTime();
Promise.all([
	d3.json(`./data/covid_data.json?t=${nowMS}`),
	d3.json("./data/geo_data.json"),
	,
]).then(objects => {
	const allCovidData: AllCovidData = objects[0];
	const allGeoData: AllGeoData = objects[1];

	assignData({ allCovidData, allGeoData });

	plotGroups.each(function () {
		const plotGroup = d3.select(this);
		initializeChoropleth({
			plotGroup,
			allCovidData,
			allGeoData,
		});
	});
});
