const plotLayout = Object.freeze({
    width: 600,
    height: 500,
});
const numberFormatter = d3.formatPrefix(",.2~s", 1e3);
const geoPaths = {
    usa: d3.geoPath(d3.geoAlbersUsa()),
};
function getPlotData(covidData, geoData, date) {
    const data = {
        cases: [],
        dates: [],
        locations: [],
        text: [],
    };
    covidData.date.forEach((d, i) => {
        if (d === date) {
            data.cases.push(covidData.cases[i]);
            data.dates.push(d);
            data.locations.push(covidData.codes[i]);
            data.text.push(covidData.names[i] + "<br>" + numberFormatter(covidData.cases[i]));
        }
    });
    console.log(data);
}
const nowMS = new Date().getTime();
Promise.all([
    d3.json(`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_usa.json"),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_world.json"),
    ,
]).then(([covidData, geoUSA, geoWorld]) => {
    const projection = d3.geoAlbersUsa().fitWidth(plotLayout.width, geoUSA);
    const path = d3.geoPath(projection);
    d3.select("#usa-1")
        .attr("width", plotLayout.width)
        .attr("height", plotLayout.height)
        .attr("background-color", "white")
        .selectAll("path")
        .data(geoUSA.features)
        .join("path")
        .attr("d", path)
        .attr("stroke", "black")
        .attr("stroke-width", 1)
        .attr("fill-opacity", 0);
    // 	.append("path")
    // 	.datum(geoUSA)
    // 	.attr("d", geoPaths.usa)
    // 	.attr("stroke", "black")
    // 	.attr("stroke-width", 0.5);
    // plotData(covidData.usa, geoUSA, "2020-05-11");
});
