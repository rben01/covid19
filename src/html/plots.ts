declare const d3: any;

interface GeoDatum {
	region_name: string;
	lat: number[];
	lon: number[];
}

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
	geo: { [key: string]: GeoDatum[] };
}

d3.json(
	"https://raw.githubusercontent.com/rben01/covid19/js-migrate/data/data.json",
).then((data: any) => {
	console.log(data);
});
