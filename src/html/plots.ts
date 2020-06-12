declare const d3: any;
declare const Plotly: any;

interface CovidDatum {
	state: string;
	county: string;
	state_code: string;
	date: string;
	cases: number;
	cases_per_capita: number;
	deaths: number;
	deaths_per_capita: number;
}

interface Data {
	records: CovidDatum[];
	geo: { [key: string]: { lat: number[]; lon: number[] } };
}

function plotData(data) {
	const data = [
		{
			type: "choropleth",
		},
	];
}

d3.json(
	"https://raw.githubusercontent.com/rben01/covid19/js-migrate/data/data.json",
).then((data: any) => {
	console.log(data);
});
