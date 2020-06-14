const numberFormatter = d3.formatPrefix(",.2~s", 1e3);
function plotData(covidData, geoData, date) {
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
    const plotData = [
        {
            type: "choropleth",
            // geojson: geoData,
            locationmode: "USA-states",
            locations: data.locations,
            z: data.cases,
            text: data.text,
            colorscale: d3.range(256).map(i => {
                const t = i / 255;
                return [t, d3.interpolateCividis(t)];
            }),
            hoverinfo: "text",
        },
    ];
    const plotLayout = {
        hoverinfo: "text",
        geo: {
            scope: "usa",
        },
        coloraxis: { showscale: false },
        margins: {
            t: 0,
            b: 0,
            l: 0,
            r: 0,
        },
    };
    Plotly.react("usa-1", plotData, plotLayout);
}
const nowMS = new Date().getTime();
Promise.all([
    d3.json(`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_usa.json"),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_world.json"),
    ,
]).then(([covidData, geoUSA, geoWorld]) => {
    plotData(covidData.usa, geoUSA, "2020-05-11");
});
