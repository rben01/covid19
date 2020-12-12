import { WORLD_LOCATIONS, } from "./types.js";
import { initializeChoropleths } from "./choropleth.js";
import { initializeLineGraph } from "./line_charts.js";
function assignData(allCovidData, allGeoData) {
    WORLD_LOCATIONS.forEach(location => {
        const scopedGeoData = allGeoData[location];
        scopedGeoData.features.forEach(feature => {
            const covidData = allCovidData[location].data[feature.properties.code];
            feature.covidData = covidData;
            if (typeof covidData === "undefined") {
                return;
            }
            feature.covidData.dodd = (() => {
                const dodd = {
                    cases: [],
                    cases_per_capita: [],
                    deaths: [],
                    deaths_per_capita: [],
                };
                for (let [caseType, data] of Object.entries(dodd)) {
                    for (let i = 0; i < Object.keys(covidData.date).length; ++i) {
                        const diff = covidData.net[caseType][i] - covidData.net[caseType][i - 1];
                        if (!diff) {
                            data.push(0);
                        }
                        else {
                            data.push(diff);
                        }
                    }
                }
                return dodd;
            })();
        });
    });
}
Promise.all([
    d3.json("./data/covid_data-6c7fd814ce8a5b6a03fdc0f8d5009ccbd5c6d498.json"),
    d3.json("./data/geo_data-be6715bfac29cf1d59f8c05b805ce8db5b42283f.json"),
]).then(objects => {
    const allCovidData = objects[0];
    const allGeoData = objects[1];
    assignData(allCovidData, allGeoData);
    d3.selectAll(".plot-placeholder").remove();
    initializeChoropleths(allCovidData, allGeoData);
    initializeLineGraph(allCovidData, allGeoData);
});
