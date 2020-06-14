const plotAesthetics = Object.freeze({
    width: 600,
    height: 300,
    colorScale: (t) => d3.interpolateOrRd(t),
    nColorSteps: 101,
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
function assignData({ allCovidData, allGeoData, }) {
    ["usa", "world"].forEach(key => {
        const geoData = allGeoData[key];
        geoData.features.forEach(feature => {
            feature.covidData = allCovidData[key].data[feature.properties.code];
        });
    });
}
function initializeMap({ svg, allCovidData, allGeoData, scope, date, caseType, }) {
    const scopedCovidData = allCovidData[scope];
    const scopedGeoData = allGeoData[scope];
    const projection = (scope === "usa"
        ? d3.geoAlbersUsa()
        : d3.geoNaturalEarth1()).fitSize([plotAesthetics.mapWidth, plotAesthetics.height], scopedGeoData);
    const path = d3.geoPath(projection);
    const colorScale = d3
        .scaleLinear()
        .domain([scopedCovidData.agg[caseType].min, scopedCovidData.agg[caseType].max])
        .range([0, 1]);
    svg.selectAll("path")
        .data(scopedGeoData.features)
        .join("path")
        .attr("d", path)
        .attr("stroke", "#fff8")
        .attr("stroke-width", 1)
        .attr("fill", (d) => {
        if (typeof d.covidData === "undefined") {
            return null;
        }
        const i = d.covidData.date.indexOf(date);
        if (i < 0) {
            return null;
        }
        return plotAesthetics.colorScale(colorScale(d.covidData[caseType][i]));
    });
    const legendTransX = plotAesthetics.mapWidth + plotAesthetics.legend.padLeft;
    const legendTransY = (plotAesthetics.height - plotAesthetics.legend.height) / 2;
    const legend = svg
        .append("g")
        .attr("transform", `translate(${legendTransX},${legendTransY})`);
    legend
        .append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", plotAesthetics.legend.barWidth)
        .attr("height", plotAesthetics.legend.height)
        .attr("fill", `url(${plotAesthetics.legend.gradientID})`);
}
const svg = d3
    .select("#usa-1")
    .attr("width", plotAesthetics.width)
    .attr("height", plotAesthetics.height)
    .attr("background-color", "white");
// Create gradient
(() => {
    const defs = svg.append("defs");
    const verticalLegendGradient = defs
        .append("linearGradient")
        .attr("id", plotAesthetics.legend.gradientID)
        .attr("x1", "0%")
        .attr("x2", "0%")
        .attr("y1", "0%")
        .attr("y2", "100%");
    d3.range(plotAesthetics.nColorSteps).forEach(i => {
        const percent = (100 * i) / (plotAesthetics.nColorSteps - 1);
        const proptn = percent / 100;
        verticalLegendGradient
            .append("stop")
            .attr("offset", `${percent}%`)
            .attr("stop-color", plotAesthetics.colorScale(proptn))
            .attr("stop-opacity", 1);
    });
})();
const nowMS = new Date().getTime();
Promise.all([
    d3.json(`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_data.json"),
    ,
]).then(objects => {
    const allCovidData = objects[0];
    const allGeoData = objects[1];
    assignData({ allCovidData, allGeoData });
    initializeMap({
        svg,
        allCovidData,
        allGeoData,
        scope: "usa",
        date: "2020-06-01",
        caseType: "cases_per_capita",
    });
    // const projection = d3
    // 	.geoAlbersUsa()
    // 	.fitSize(
    // 		[plotAesthetics.width - plotAesthetics.legendWidth, plotAesthetics.height],
    // 		geoUSA,
    // 	);
    // const path = d3.geoPath(projection);
    // const date = "2020-06-05";
    // const caseType = "cases_per_capita";
    // const colorScale = d3
    // 	.scaleLinear()
    // 	.domain([
    // 		allCovidData.usa.agg[caseType].min,
    // 		allCovidData.usa.agg[caseType].max,
    // 	])
    // 	.range([0, 1]);
    // svg.selectAll("path")
    // 	.data(geoUSA.features)
    // 	.join("path")
    // 	.attr("d", path)
    // 	.attr("stroke", "#fff8")
    // 	.attr("stroke-width", 1)
    // 	.attr("fill", (d: Feature) => {
    // 		if (typeof d.covidData === "undefined") {
    // 			return null;
    // 		}
    // 		const i = d.covidData.date.indexOf(date);
    // 		if (i < 0) {
    // 			return null;
    // 		}
    // 		return plotAesthetics.colorScale(colorScale(d.covidData[caseType][i]));
    // 	});
    // svg.call(
    // 	d3.zoom().on("zoom", function () {
    // 		svg.selectAll("path").attr("transform", d3.event.transform);
    // 	}),
    // );
    // 	.append("path")
    // 	.datum(geoUSA)
    // 	.attr("d", geoPaths.usa)
    // 	.attr("stroke", "black")
    // 	.attr("stroke-width", 0.5);
    // plotData(covidData.usa, geoUSA, "2020-05-11");
});
