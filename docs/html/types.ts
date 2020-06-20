export type DateString = string;
export type CaseType = "cases" | "cases_per_capita" | "deaths" | "deaths_per_capita";
export type WorldLocation = "usa" | "world";
export type CountMethod = "net" | "dodd";
export interface Scope {
	location: WorldLocation;
	count: CountMethod;
}
// type Scope = { location: "usa"; count: "net" } | { location: "world"; count: "net" };

export const WORLD_LOCATIONS: WorldLocation[] = ["usa", "world"];
export const COUNT_METHODS: CountMethod[] = ["dodd", "net"];
export const SCOPES: Scope[] = (() => {
	const scopes: Scope[] = [];
	COUNT_METHODS.forEach((count: CountMethod) => {
		WORLD_LOCATIONS.forEach((location: WorldLocation) => {
			scopes.push({ location, count });
		});
	});
	return scopes;
})();

export interface AllGeoData {
	usa: ScopedGeoData;
	world: ScopedGeoData;
}

export interface ScopedGeoData {
	type: string;
	features: Feature[];
}

export interface Feature {
	properties: {
		code: string;
		name: string;
	};
	covidData: LocationCovidData;
}

// usa/world -> "data" -> state/country -> date -> data
export interface AllCovidData {
	usa: ScopedCovidData;
	world: ScopedCovidData;
}

export interface Aggregated<T> {
	min: T;
	min_nonzero: T;
	max: T;
}

export type AggNumber = Aggregated<number>;
export type AggDate = Aggregated<DateString>;

export interface ScopedCovidData {
	agg: {
		[key: string]: {
			cases: AggNumber;
			cases_per_capita: AggNumber;
			deaths: AggNumber;
			deaths_per_capita: AggNumber;
			date: AggDate;
		};
	};
	data: {
		[key: string]: LocationCovidData;
	};
}

export interface DataGroup {
	cases: number[];
	cases_per_capita: number[];
	deaths: number[];
	deaths_per_capita: number[];
}

export interface LocationCovidData extends DataGroup {
	date: { [key: string]: number };
	day_over_day_diffs: DataGroup;
}

export interface PlotInfo {
	location: WorldLocation;
	count: CountMethod;
	caseType: CaseType;
	scopedCovidData?: ScopedCovidData;
	plotGroup?: any;
}
