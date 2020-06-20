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
            feature.covidData.day_over_day_diffs = (() => {
                const dodd = {
                    cases: [],
                    cases_per_capita: [],
                    deaths: [],
                    deaths_per_capita: [],
                };
                for (let [caseType, data] of Object.entries(dodd)) {
                    for (let i = 0; i < Object.keys(covidData.date).length; ++i) {
                        const diff = covidData[caseType][i] - covidData[caseType][i - 1];
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
    d3.json("./data/covid_data-ec2fa8fb9a8f76497ba5cfbb11ce481dc2812362.json"),
    d3.json("./data/geo_data.json"),
]).then(objects => {
    const allCovidData = objects[0];
    const allGeoData = objects[1];
    assignData(allCovidData, allGeoData);
    initializeChoropleths(allCovidData, allGeoData);
    initializeLineGraph(allCovidData, allGeoData);
});
