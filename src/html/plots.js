function rollingAverage(data) {}

d3.json(
	"https://raw.githubusercontent.com/rben01/covid19/js-migrate/data/data.json",
).then(data => {
	console.log(data);
});
