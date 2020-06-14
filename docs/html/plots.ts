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

interface AggData {
	min: number;
	min_nonzero: number;
	max: number;
}

interface ScopedCovidData {
	agg: {
		cases: AggData;
		cases_per_capita: AggData;
		deaths: AggData;
		deaths_per_capita: AggData;
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

const plotAesthetics = Object.freeze({
	width: 600,
	height: 300,
	colors: {
		scale: d3.interpolateCividis,
		nSteps: 101,
		missing: "#ccc",
	},
	legend: {
		padLeft: 40,
		barWidth: 20,
		padRight: 40,
		height: 250,
		gradientID: "verticalLegendGradient",
	},

	get mapWidth() {
		const legend = this.legend;
		return this.width - (legend.padLeft + legend.barWidth + legend.padRight);
	},
});

const numberFormatter = d3.formatPrefix(",.2~s", 1e3);

const geoPaths = {
	usa: d3.geoPath(d3.geoAlbersUsa()),
};

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
	).fitSize([plotAesthetics.mapWidth, plotAesthetics.height], scopedGeoData);
	const path = d3.geoPath(projection);

	const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];

	const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);

	svg.selectAll("path")
		.data(scopedGeoData.features)
		.join("path")
		.attr("d", path)
		.attr("stroke", "#fff8")
		.attr("stroke-width", 1)
		.attr("fill", (d: Feature) => {
			if (typeof d.covidData === "undefined") {
				return plotAesthetics.colors.missing;
			}
			const i = d.covidData.date.indexOf(date);
			if (i < 0) {
				return plotAesthetics.colors.missing;
			}
			return plotAesthetics.colors.scale(colorScale(d.covidData[caseType][i]));
		});

	const legendTransX = plotAesthetics.mapWidth + plotAesthetics.legend.padLeft;
	const legendTransY = (plotAesthetics.height - plotAesthetics.legend.height) / 2;
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

	const formatter = legendScale.tickFormat(8);
	legendScale.ticks(8).forEach((y: number) => {
		console.log(formatter(y));
		legend
			.append("text")
			.attr("x", barWidth)
			.attr("y", legendScale(y))
			.text(`${formatter(y)}`)
			.attr("fill", "black")
			.attr("font-size", 12)
			.attr("font-family", "sans-serif")
			.attr("text-anchor", "left")
			.attr("alignment-baseline", "middle");
	});
}

const svg = d3
	.select("#usa-1")
	.attr("width", plotAesthetics.width)
	.attr("height", plotAesthetics.height)
	.attr("background-color", "black");

// Create gradient
(() => {
	const defs = svg.append("defs");
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

	initializeMap({
		svg,
		allCovidData,
		allGeoData,
		scope: "usa",
		date: "2020-06-09",
		caseType: "cases_per_capita",
	});

	// svg.call(
	// 	d3.zoom().on("zoom", function () {
	// 		svg.selectAll("path").attr("transform", d3.event.transform);
	// 	}),
	// );
});
