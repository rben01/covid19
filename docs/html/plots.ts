declare const d3: any;

type DateString = string;
type CaseType = "cases" | "cases_per_capita" | "deaths" | "deaths_per_capita";
type Scope = "usa" | "world";

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
}

const MS_PER_DAY = 86400 * 1000;

const plotAesthetics = Object.freeze({
	width: { usa: 500, world: 600 },
	height: { usa: 350, world: 400 },
	colors: {
		scale: (t: number) => d3.interpolateCividis(1 - t),
		nSteps: 101,
		missing: "#ccc",
		zero: "#ddc",
	},
	legend: {
		padLeft: 20,
		barWidth: 15,
		padRight: 40,
		height: 275,
		gradientID: "verticalLegendGradient",
	},
	title: {
		height: 40,
	},

	get mapWidth() {
		const legend = this.legend;
		const mw = {};
		Object.keys(this.width).forEach((scope: Scope) => {
			const width = this.width[scope];
			mw[scope] = width - (legend.padLeft + legend.barWidth + legend.padRight);
		});
		return mw;
	},
});

function isPerCapita(caseType: CaseType) {
	return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}

const dateStrParser = d3.timeParse("%Y-%m-%d");
const dateFormatter = d3.timeFormat("%Y-%m-%d");
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
	["usa", "world"].forEach(key => {
		const scopedGeoData: ScopedGeoData = allGeoData[key];
		scopedGeoData.features.forEach(feature => {
			feature.covidData = allCovidData[key].data[feature.properties.code];
		});
	});
}

function updateMaps({ plotGroup, dateIndex }: { plotGroup: any; dateIndex?: number }) {
	plotGroup.selectAll(".date-slider").property("value", dateIndex);

	const minDate = plotGroup.datum().scopedCovidData.agg.date.min_nonzero;
	const dateKey = getDateNDaysAfter(minDate, dateIndex);

	const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
	const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
	plotGroup.selectAll(".date-span").text(dateStr);

	console.log(dateKey, trueDate);

	plotGroup
		.selectAll(".plot-container")
		.each(function ({
			caseType,
			vmin,
			vmax,
		}: {
			caseType: CaseType;
			vmin: number;
			vmax: number;
		}) {
			const plotContainer = d3.select(this);
			const formatter = isPerCapita(caseType)
				? numberFormatters.float
				: numberFormatters.int;

			const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);

			const svg = plotContainer.selectAll("svg");
			svg.selectAll("path")
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
				.on("mouseover", (d: Feature) => {
					const noDataStr = "~No data~";

					const caseCount = (() => {
						if (typeof d.covidData === "undefined") {
							return noDataStr;
						}

						const index = d.covidData.date[dateKey];
						if (typeof index === "undefined") {
							return noDataStr;
						}

						return formatter(d.covidData[caseType][index]);
					})();

					tooltip.html(`${dateKey}<br>${d.properties.name}<br>${caseCount}`);
					return tooltip.style("visibility", "visible");
				})
				.on("mousemove", () =>
					tooltip
						.style("top", `${+d3.event.pageY - 30}px`)
						.style("left", `${+d3.event.pageX + 10}px`),
				)
				.on("mouseout", () => tooltip.style("visibility", "hidden"));
		});
}

const numberFormatters = { int: d3.format(",~r"), float: d3.format(",.2f") };

const tooltip = d3.select("body").append("div").attr("id", "tooltip");

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

	plotGroup.datum({ ...plotGroup.datum(), scopedCovidData });

	const legendTransX = plotAesthetics.mapWidth[scope] + plotAesthetics.legend.padLeft;
	const legendTransY =
		(plotAesthetics.title.height +
			plotAesthetics.height[scope] -
			plotAesthetics.legend.height) /
		2;
	const { min_nonzero: minDate, max: maxDate } = scopedCovidData.agg.date;
	const firstDay = dateStrParser(minDate);
	const lastDay = dateStrParser(maxDate);
	const daysElapsed = Math.round((lastDay - firstDay) / MS_PER_DAY);

	plotGroup.selectAll(".plot-container").each(function () {
		const plotContainer = d3.select(this);
		const caseType = plotContainer.datum().caseType;
		const svg = plotContainer.selectAll("svg");

		const projection = (scope === "usa"
			? d3.geoAlbersUsa()
			: d3.geoNaturalEarth1()
		).fitExtent(
			[
				[0, plotAesthetics.title.height],
				[plotAesthetics.mapWidth[scope], plotAesthetics.height[scope]],
			],
			scopedGeoData,
		);
		const path = d3.geoPath(projection);

		svg.selectAll("path")
			.data(scopedGeoData.features)
			.join("path")
			.attr("d", path)
			.attr("stroke", "#fff8")
			.attr("stroke-width", 1);

		const legend = svg
			.append("g")
			.attr("transform", `translate(${legendTransX},${legendTransY})`);

		const { barWidth, height: barHeight } = plotAesthetics.legend;
		legend
			.append("rect")
			.attr("x", 0)
			.attr("y", 0)
			.attr("width", barWidth)
			.attr("height", barHeight)
			.attr("fill", `url(#${plotAesthetics.legend.gradientID})`);

		const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];
		plotContainer.datum({ ...plotContainer.datum(), vmin, vmax });
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
			this.value = daysElapsed;
		});
	});

	updateMaps({ plotGroup, dateIndex: daysElapsed });
}

const plotGroups = d3
	.select("#content")
	.selectAll()
	.data([{ scope: "usa" }, { scope: "world" }])
	.join("div")
	.classed("plot-scope-group", true);

const plotDivs = plotGroups
	.selectAll()
	.data(({ scope }: { scope: Scope }) => {
		const data = [];
		["cases", "cases_per_capita", "deaths", "deaths_per_capita"].forEach(
			(caseType: CaseType) => {
				data.push({ scope, caseType });
			},
		);
		return data;
	})
	.join("div")
	.classed("plot-container", true);

const svgs = plotDivs
	.append("svg")
	.attr("width", (d: PlotInfo) => plotAesthetics.width[d.scope])
	.attr("height", (d: PlotInfo) => plotAesthetics.height[d.scope]);

const sliderRow = plotDivs.append("div").append("span");
const sliders = sliderRow
	.append("input")
	.classed("date-slider", true)
	.attr("type", "range")
	.attr("min", 0)
	.attr("max", 1)
	.property("value", 1)
	.on("input", function (d: PlotInfo) {
		console.log("h");
		const plotGroup = plotGroups.filter((p: PlotInfo) => p.scope === d.scope);
		const dateIndex = +this.value;
		updateMaps({ plotGroup, dateIndex });
	});

const dateSpans = sliderRow.append("span").classed("date-span", true);

const buttonsRow = plotDivs.append("div").append("span");
buttonsRow.append("button").classed("play-button", true);

// Create gradient
(() => {
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
