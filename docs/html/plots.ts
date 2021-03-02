declare const d3: any;

import {
	AllCovidData,
	AllGeoData,
	CaseType,
	LocationCovidData,
	ScopedGeoData,
	WORLD_LOCATIONS,
} from "./types.js";

import { initializeChoropleths } from "./choropleth.js";
import { initializeLineGraph } from "./line_charts.js";

function assignData(allCovidData: AllCovidData, allGeoData: AllGeoData) {
	WORLD_LOCATIONS.forEach(location => {
		const scopedGeoData: ScopedGeoData = allGeoData[location];
		scopedGeoData.features.forEach(feature => {
			const covidData: LocationCovidData =
				allCovidData[location].data[feature.properties.code];
			feature.covidData = covidData;

			if (covidData === undefined) {
				return;
			}

			const nDates = Object.keys(covidData.date).length;
			feature.covidData.dodd = (() => {
				const dodd: { [key in CaseType]: number[] } = {
					cases: [],
					cases_per_capita: [],
					deaths: [],
					deaths_per_capita: [],
				};

				for (let [caseType, data] of Object.entries(dodd) as [
					CaseType,
					number[],
				][]) {
					for (let i = 0; i < nDates; ++i) {
						const diff =
							covidData.net[caseType][i] - covidData.net[caseType][i - 1];
						if (isNaN(diff)) {
							data.push(0);
						} else {
							data.push(diff);
						}
					}
				}

				return dodd;
			})();
		});
	});
}

// Use the custom digest of the data file to only pull from the web anew, ignoring browser cache, when data has actually updated
Promise.all([
	d3.json("./data/covid_data-73acdb20538f6f8b5e1c50442e7479407e6a108e.json"),
	d3.json("./data/geo_data-be6715bfac29cf1d59f8c05b805ce8db5b42283f.json"),
]).then(objects => {
	const allCovidData: AllCovidData = objects[0];
	const allGeoData: AllGeoData = objects[1];

	d3.selectAll(".initial-plot-area").style("min-height", null);
	// const startMS = new Date().getTime();
	// function logElapsedMS() {
	// 	console.log(new Date().getTime() - startMS);
	// }

	// logElapsedMS();
	assignData(allCovidData, allGeoData);
	// logElapsedMS();

	initializeChoropleths(allCovidData, allGeoData);
	// logElapsedMS();
	initializeLineGraph(allCovidData, allGeoData);
	// logElapsedMS();
});
