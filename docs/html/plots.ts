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
	records: {
		state?: string[];
		state_code?: string[];
		country?: string[];
		date: string[];
		cases: number[];
		cases_per_capita: number[];
		deaths: number[];
		deaths_per_capita: number[];
	};
	geo: GeoJson;
}

interface DateString {}

function plotData(covidData: Data, date: DateString) {
	const data = {
		cases: [],
		dates: [],
		location: [],
	};
	covidData.records.date.forEach((d, i) => {
		if (d === date) {
			data.cases.push(covidData.records.cases[i]);
			data.dates.push(d);
			data.location
		}
	});

	const plotData = [
		{
			type: "choropleth",
			geojson: covidData.geo,
			z,
		},
	];

	Plotly.react(data);
}

const nowMS = new Date().getTime();
d3.json(
	`https://raw.githubusercontent.com/rben01/covid19/js-migrate/data/data.json?t=${nowMS}`,
).then((data: any) => {
	console.log(data);
});
