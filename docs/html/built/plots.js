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
            data.text.push(covidData.names[i]);
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
        },
    ];
    const plotLayout = {
        geo: {
            scope: "usa",
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
Plotly.d3.csv("https://raw.githubusercontent.com/plotly/datasets/master/2011_us_ag_exports.csv", function (err, rows) {
    function unpack(rows, key) {
        return rows.map(function (row) {
            return row[key];
        });
    }
    var data = [
        {
            type: "choropleth",
            locationmode: "USA-states",
            locations: unpack(rows, "code"),
            z: unpack(rows, "total exports"),
            text: unpack(rows, "state"),
            zmin: 0,
            zmax: 17000,
            colorscale: [
                [0, "rgb(242,240,247)"],
                [0.2, "rgb(218,218,235)"],
                [0.4, "rgb(188,189,220)"],
                [0.6, "rgb(158,154,200)"],
                [0.8, "rgb(117,107,177)"],
                [1, "rgb(84,39,143)"],
            ],
            colorbar: {
                title: "Millions USD",
                thickness: 0.2,
            },
            marker: {
                line: {
                    color: "rgb(255,255,255)",
                    width: 2,
                },
            },
        },
    ];
    var layout = {
        title: "2011 US Agriculture Exports by State",
        geo: {
            scope: "usa",
            showlakes: true,
            lakecolor: "rgb(255,255,255)",
        },
    };
    Plotly.newPlot("usa-2", data, layout, { showLink: false });
});
