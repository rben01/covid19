declare const d3: any;

type DateString = string;
type CaseType = "cases" | "cases_per_capita" | "deaths" | "deaths_per_capita";
type Scope = "usa" | "world";

const SCOPES = ["usa", "world"];

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
		cases: AggNumber;
		cases_per_capita: AggNumber;
		deaths: AggNumber;
		deaths_per_capita: AggNumber;
		date: AggDate;
	};
	data: {
		[key: string]: {
			[key: string]: LocationCovidData;
		};
	};
}

interface LocationCovidData {
	date: string[];
	cases: number[];
	cases_per_capita: number[];
	deaths: number[];
	deaths_per_capita: number[];
}

interface PlotInfo {
	scope: Scope;
	caseType: CaseType;
	scopedCovidData?: ScopedCovidData;
	plotGroup?: any;
}

const MS_PER_DAY = 86400 * 1000;

const plotAesthetics = Object.freeze(
	(() => {
		const pa = {
			width: { usa: 600, world: 600 },
			height: { usa: 425, world: 350 },
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
				height: { usa: 350, world: 275 },
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
		Object.keys(pa.width).forEach((scope: Scope) => {
			pa.mapWidth[scope] =
				pa.width[scope] -
				pa.map.originX -
				(pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight) -
				pa.map.pad;
		});

		pa.mapHeight = {};
		Object.keys(pa.height).forEach((scope: Scope) => {
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
	SCOPES.forEach(key => {
		const scopedGeoData: ScopedGeoData = allGeoData[key];
		scopedGeoData.features.forEach(feature => {
			feature.covidData = allCovidData[key].data[feature.properties.code];
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

function getFormatter(caseType: CaseType) {
	return isPerCapita(caseType) ? numberFormatters.float : numberFormatters.int;
}

type Visibility = "visible" | "hidden" | "nochange";
function updateTooltip({ visibility }: { visibility: Visibility }) {
	const { feature, dateKey, caseType } = tooltip.datum();

	if (typeof feature === "undefined") {
		return;
	}

	const dateStr = tooltipDateFormatter(dateStrParser(dateKey).getTime() - MS_PER_DAY);

	const location = feature.properties.name;

	const countStr = (() => {
		const noDataStr = "~No data~";
		if (typeof feature.covidData === "undefined") {
			return noDataStr;
		}

		const index = feature.covidData.date[dateKey];
		if (typeof index === "undefined") {
			return noDataStr;
		}

		const formatter = getFormatter(caseType);
		return formatter(feature.covidData[caseType][index]);
	})();

	tooltip.html(`${dateStr}<br>${location}<br>${countStr}`);
	if (visibility !== "nochange") {
		tooltip.style("visibility", visibility);
	}
}

let mouseMoved = false;

function updateMaps({ plotGroup, dateIndex }: { plotGroup: any; dateIndex: number }) {
	const sliderNode = plotGroup
		.selectAll(".date-slider")
		.property("value", dateIndex)
		.node();

	const minDate = plotGroup.datum().scopedCovidData.agg.date.min_nonzero;
	const dateKey = getDateNDaysAfter(minDate, dateIndex);

	const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
	const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
	plotGroup.selectAll(".date-span").text(dateStr);

	tooltip.datum({ ...tooltip.datum(), dateKey });
	updateTooltip({ visibility: "nochange" });

	plotGroup
		.selectAll(".plot-container")
		.each(function ({
			caseType,
			plotGroup,
		}: {
			caseType: CaseType;
			plotGroup: any;
		}) {
			const plotContainer = d3.select(this);

			const {
				min_nonzero: vmin,
				max: vmax,
			} = plotGroup.datum().scopedCovidData.agg[caseType];
			const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);

			const svg = plotContainer.selectAll("svg").selectAll(".map");

			mouseActions.mouseover = (d: Feature) => {
				tooltip.datum({ ...tooltip.datum(), feature: d, caseType });
				updateTooltip({ visibility: "visible" });
			};
			mouseActions.mousemove = () => {
				if (!mouseMoved) {
					const dateIndex = +sliderNode.value;
					tooltip.datum({
						...tooltip.datum(),
						dateKey: getDateNDaysAfter(minDate, dateIndex),
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
				.attr("fill", (d: Feature) => {
					if (typeof d.covidData === "undefined") {
						return plotAesthetics.colors.missing;
					}
					const index = d.covidData.date[dateKey];
					if (typeof index === "undefined") {
						return plotAesthetics.colors.missing;
					}

					const value = d.covidData[caseType][index];
					if (value < vmin) {
						return plotAesthetics.colors.zero;
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
		dateKey?: DateString;
		caseType?: CaseType;
	}) => { feature: Feature; dateKey: DateString; caseType: CaseType };
	style: any;
	attr: any;
	html: any;
} = d3
	.select("body")
	.selectAll()
	.data([{ dateKey: null, location: null, countStr: null }])
	.join("div")
	.attr("id", "tooltip");

// https://bl.ocks.org/mthh/8f97dda227d21163773b0a714a573856
function dispatchMouseToMap(event, type) {
	const { pageX, pageY, clientX, clientY } = event;
	const elems = document.elementsFromPoint(pageX, pageY);
	const elem = elems.find(e => d3.select(e).classed("state-boundary"));

	if (elem) {
		d3.select(elem).each((d: any) => mouseActions.mouseover(d));
		const new_click_event = new MouseEvent(type, {
			pageX: pageX,
			pageY: pageY,
			clientX: clientX,
			clientY: clientY,
			bubbles: true,
			cancelable: true,
			view: window,
		} as any);
		elem.dispatchEvent(new_click_event);
	} else {
		mouseActions.mouseout();
		// clearTimeout(t);
		// t = setTimeout(() => {
		// 	svg.select(".tooltip").style("display", "none");
		// }, 5);
	}
}

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
	const scope = plotGroup.datum().scope;
	const scopedCovidData: ScopedCovidData = allCovidData[scope];
	const scopedGeoData: ScopedGeoData = allGeoData[scope];

	const projectionExtent = [
		[0, 0],
		[
			plotAesthetics.mapWidth[scope] - plotAesthetics.map.pad,
			plotAesthetics.mapHeight[scope] - plotAesthetics.map.pad,
		],
	];
	const projection = (scope === "usa"
		? d3.geoAlbersUsa()
		: d3.geoCylindricalStereographic()
	).fitExtent(projectionExtent, scopedGeoData);

	const path = d3.geoPath(projection);

	const zoom = d3
		.zoom()
		.scaleExtent([1, plotAesthetics.map.maxZoom[scope]])
		.translateExtent([
			[0, 0],
			[plotAesthetics.width[scope], plotAesthetics.height[scope]],
		])
		.filter(function () {
			return (
				d3.event.type !== "dblclick" &&
				(d3.event.type !== "wheel" || d3.event.ctrlKey) &&
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
				// Holy race condition Batman (JS is single threaded so it's fine; graphHasBegunZooming = false can't run before all the other zooms have been applied)
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

			// const mapContainer = this;
			// plotGroup.selectAll(".map").each(function () {
			// 	console.log(this, d3.event.sourceEvent);
			// 	if (d3.event.sourceEvent.target == this) {
			// 		d3.select(this).call(zoom.transform, transform);
			// 	} else {
			// 		d3.select(mapContainer)
			// 			.selectAll(".map")
			// 			.attr("transform", transform);
			// 	}
			// });

			// plotGroup.selectAll(".map").attr("transform", transform);
			// 	.each(function () {});
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

	const legendTransX = plotAesthetics.mapWidth[scope] + plotAesthetics.legend.padLeft;
	const legendTransY =
		(plotAesthetics.title.height +
			plotAesthetics.height[scope] -
			plotAesthetics.legend.height[scope]) /
		2;
	const { min_nonzero: minDate, max: maxDate } = scopedCovidData.agg.date;
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
			.attr("width", plotAesthetics.mapWidth[scope])
			.attr("height", plotAesthetics.mapHeight[scope])
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
		const barHeight = barHeights[scope];
		legend
			.append("rect")
			.attr("x", 0)
			.attr("y", 0)
			.attr("width", barWidth)
			.attr("height", barHeight)
			.attr("fill", `url(#${plotAesthetics.legend.gradientID})`);

		const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];
		const legendScale = d3
			.scaleLog()
			.nice()
			.base(10)
			.domain([vmin, vmax])
			.range([barHeight, 0]);

		legendScale.ticks(8).forEach((y: number) => {
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

		const fmtStr = isPerCapita(caseType) ? "~g" : "~s";
		const tickFormatter = legendScale.tickFormat(7, fmtStr);
		legendScale.ticks(7).forEach((y: number) => {
			legend
				.append("text")
				.attr("x", barWidth + 4)
				.attr("y", legendScale(y))
				.text(`${tickFormatter(y)}`)
				.attr("fill", "black")
				.attr("font-size", 12)
				.attr("font-family", "sans-serif")
				.attr("text-anchor", "left")
				.attr("alignment-baseline", "middle");
		});

		let caseTypeStr = caseType;
		let suffixStr = "";
		if (isPerCapita(caseTypeStr)) {
			caseTypeStr = caseTypeStr.replace("_per_capita", "");
			suffixStr = " Per 100,000 People";
		}
		caseTypeStr = caseTypeStr.replace(/^./, (c: string) => c.toUpperCase());

		const titleStr = `Total ${caseTypeStr}${suffixStr}`;
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

	updateMaps({ plotGroup, dateIndex: daysElapsed });
}

const plotGroups = d3
	.select("#content")
	.selectAll()
	.data(
		SCOPES.map(scope => {
			return { scope };
		}),
	)
	.join("div")
	.classed("plot-scope-group", true);

const plotContainers = plotGroups
	.selectAll()
	.data(function ({ scope }: { scope: Scope }) {
		return ["cases", "cases_per_capita", "deaths", "deaths_per_capita"].map(
			(caseType: CaseType) => ({
				scope,
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
	.attr("width", (d: PlotInfo) => plotAesthetics.width[d.scope])
	.attr("height", (d: PlotInfo) => plotAesthetics.height[d.scope]);

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
	plotGroups.each(function () {
		const plotGroup = d3.select(this);
		const sliderRows = plotGroup
			.selectAll(".plot-container")
			.append("div")
			.append("span");
		sliderRows.append("span").classed("date-span", true);
		sliderRows
			.selectAll()
			.data(() => [{ plotGroup }])
			.join("input")
			.classed("date-slider", true)
			.attr("type", "range")
			// Temporary values, used to place the slider's knob to the right while we await the actual data we'll use to compute its range
			.attr("min", 0)
			.attr("max", 1)
			.property("value", 1)
			.on("input", function (d: PlotInfo) {
				const dateIndex = +this.value;
				updateMaps({ plotGroup: d.plotGroup, dateIndex });
			});

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

		const sliders = plotGroup.selectAll(".date-slider");
		const sliderNode = sliders.node();

		function haltPlayback(playbackInfo: PlaybackInfo) {
			playbackInfo.isPlaying = false;
			clearInterval(playbackInfo.timer);
			const now = new Date();
			const elapsedTimeMS = now.getTime() - playbackInfo.timerStartDate.getTime();
			playbackInfo.timerElapsedTimeProptn +=
				elapsedTimeMS / playbackInfo.currentIntervalMS;
		}

		function startPlayback(playbackInfo: PlaybackInfo) {
			if (sliderNode.value === sliderNode.max) {
				updateMaps({ plotGroup, dateIndex: 0 });
				// A number indistinguishable from 0 (except to a computer)
				playbackInfo.timerElapsedTimeProptn = 0.0000001;
			}

			playbackInfo.isPlaying = true;
			function updateDate() {
				playbackInfo.timerStartDate = new Date();
				playbackInfo.timerElapsedTimeProptn = 0;

				const dateIndex = parseFloat(sliderNode.value);
				if (dateIndex < parseFloat(sliderNode.max)) {
					updateMaps({ plotGroup, dateIndex: dateIndex + 1 });
				} else {
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

		function onPlaybackButtonClick(playbackInfo: PlaybackInfo) {
			if (playbackInfo.isPlaying) {
				playButtons.text("Play");
				haltPlayback(playbackInfo);
			} else {
				playButtons.text("Pause");
				startPlayback(playbackInfo);
			}
		}

		playButtons.on("click", function (playbackInfo: PlaybackInfo) {
			onPlaybackButtonClick(playbackInfo);
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
			console.log(wasPlaying);
			if (wasPlaying) {
				startPlayback(playbackInfo);
			}
		});
	});
})();

// Create defs: gradient and clipPath
(() => {
	plotGroups.each(function ({ scope }: { scope: Scope }) {
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
		const clipPathID = `plot-clip-${scope}`;
		defs.append("clipPath")
			.attr("id", clipPathID)
			.append("rect")
			.attr("x", plotAesthetics.map.originX)
			.attr("y", plotAesthetics.map.originY)
			.attr("width", plotAesthetics.mapWidth[scope])
			.attr("height", plotAesthetics.mapHeight[scope]);
		canvases.attr("clip-path", `url(#${clipPathID})`);
	});
})();

const nowMS = new Date().getTime();
Promise.all([
	d3.json(
		`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`,
	),
	d3.json(
		"https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_data.json",
	),
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
