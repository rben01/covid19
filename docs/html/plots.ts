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
	name: string;
	date: string[];
	cases: number[];
	cases_per_capita: number[];
	deaths: number[];
	deaths_per_capita: number[];
}

interface PlotState {
	caseType: CaseType;
	scopedCovidData: ScopedCovidData;
}

const plotAesthetics = Object.freeze({
	width: { usa: 500, world: 650 },
	height: { usa: 350, world: 400 },
	colors: {
		scale: d3.interpolateCividis,
		nSteps: 101,
		missing: "#ccc",
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

function assignData({
	allCovidData,
	allGeoData,
}: {
	allCovidData: AllCovidData;
	allGeoData: AllGeoData;
}) {
	["usa", "world"].forEach(key => {
		const geoData: ScopedGeoData = allGeoData[key];
		geoData.features.forEach(feature => {
			feature.covidData = allCovidData[key].data[feature.properties.code];
		});
	});
}

function updateMap({ svg, date }: { svg: any; date: DateString }) {
	const plotState: PlotState = svg.datum();
	const { caseType, scopedCovidData } = plotState;
	const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];
	const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);
	svg.selectAll("path")
		.attr("fill", (d: Feature) => {
			if (typeof d.covidData === "undefined") {
				return plotAesthetics.colors.missing;
			}
			const i = d.covidData.date.indexOf(date);
			if (i < 0) {
				return plotAesthetics.colors.missing;
			}
			return plotAesthetics.colors.scale(colorScale(d.covidData[caseType][i]));
		})
		.on("mouseover", function (d: Feature) {
			if (typeof d.covidData === "undefined") {
				return tooltip.style("visibility", "visible");
			}
			const i = d.covidData.date.indexOf(date);
			const caseCount =
				i >= 0 ? numberFormatter(d.covidData[caseType][i]) : "No data";
			tooltip.html(`${date}<br>${d.covidData.name}<br>${caseCount}`);
			return tooltip.style("visibility", "visible");
		})
		.on("mousemove", function () {
			return tooltip
				.style("top", `${+d3.event.pageY - 10}px`)
				.style("left", `${+d3.event.pageX + 10}px`);
		})
		.on("mouseout", function () {
			return tooltip.style("visibility", "hidden");
		});
}

const numberFormatter = d3.formatPrefix(",.2~s", 1e3);

const tooltip = d3
	.select("body")
	.append("div")
	.style("position", "absolute")
	.style("z-index", "100")
	.style("visibility", "hidden")
	.style("background", "#fffd")
	.style("color", "#111")
	.style("border-radius", "2px")
	.style("border-width", "2px")
	.style("border-color", "#111")
	.style("border-style", "solid")

	.style("font-family", "sans-serif")
	.style("font-size", "12px")
	.style("padding", "2px");

function initializeMap({
	svg,
	allCovidData,
	allGeoData,
	scope,
	date,
	caseType,
}: {
	svg: any;
	allCovidData: AllCovidData;
	allGeoData: AllGeoData;
	scope: Scope;
	date: DateString;
	caseType: CaseType;
}) {
	const scopedCovidData = allCovidData[scope];
	const scopedGeoData = allGeoData[scope];

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

	const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];

	svg.datum({ caseType, scopedCovidData });

	svg.selectAll("path")
		.data(scopedGeoData.features)
		.join("path")
		.attr("d", path)
		.attr("stroke", "#fff8")
		.attr("stroke-width", 1);

	updateMap({ svg, date });

	const legendTransX = plotAesthetics.mapWidth[scope] + plotAesthetics.legend.padLeft;
	const legendTransY =
		(plotAesthetics.title.height +
			plotAesthetics.height[scope] -
			plotAesthetics.legend.height) /
		2;
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

	const fmtStr = caseType.includes("per_capita") ? "~g" : "~s";
	const formatter = legendScale.tickFormat(7, fmtStr);
	legendScale.ticks(7).forEach((y: number) => {
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

	let caseTypeStr = caseType.replace(/^./, c => c.toUpperCase());
	let suffixStr = "";
	if (caseTypeStr.includes("_per_capita")) {
		caseTypeStr = caseTypeStr.replace("_per_capita", "");
		suffixStr = " Per 100,000 People";
	}

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
}

const svgs = d3
	.selectAll(".plot")
	.attr("width", function () {
		return plotAesthetics.width[this.getAttribute("_scope")];
	})
	.attr("height", function () {
		return plotAesthetics.height[this.getAttribute("_scope")];
	});
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
	d3.range(plotAesthetics.colors.nSteps).forEach(i => {
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

	svgs.each(function () {
		const svg = d3.select(this);
		initializeMap({
			svg,
			allCovidData,
			allGeoData,
			scope: svg.attr("_scope"),
			date: allCovidData.usa.agg.date.max,
			caseType: svg.attr("_case_type"),
		});
	});
});
