declare const d3: any;
declare const Plotly: any;

interface CovidDatum {
	state: string;
	country: string;
	state_code: string;
	date: string;
	cases: number;
	cases_per_capita: number;
	deaths: number;
	deaths_per_capita: number;
}

interface GeoJson {}

interface Data {
	names: string[];
	codes: string[];
	state?: string[];
	state_code?: string[];
	country?: string[];
	date: string[];
	cases: number[];
	cases_per_capita: number[];
	deaths: number[];
	deaths_per_capita: number[];
}

interface DateString {}

function plotData(covidData: Data, geoData: GeoJson, date: DateString) {
	const data = {
		cases: [],
		dates: [],
		location: [],
		text: [],
	};
	covidData.date.forEach((d, i) => {
		if (d === date) {
			data.cases.push(covidData.cases[i]);
			data.dates.push(d);
			data.location.push(covidData.codes[i]);
			data.text.push(covidData.names[i]);
		}
	});
	console.log(data);

	const plotData = [
		{
			type: "choropleth",
			geojson: geoData,
			featureidkey: "properties.ADM0_A3",
			z: data.cases,
			text: data.text,
		},
	];

	Plotly.react("usa-1", plotData);
}

const nowMS = new Date().getTime();
Promise.all([
	d3.json(
		`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`,
	),
	d3.json(
		"https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_usa.json",
	),
	d3.json(
		"https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_world.json",
	),
	,
]).then(([covidData, geoUsa, geoWorld]) => {
	plotData(covidData.world, geoWorld, "2020-05-11");
	console.log("here");
});
