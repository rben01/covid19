function plotData(data) {
    // const data = [
    // 	{
    // 		type: "choropleth",
    // 	},
    // ];
}
const nowMS = new Date().getTime();
d3.json(`https://raw.githubusercontent.com/rben01/covid19/js-migrate/data/data.json?t=${nowMS}`).then((data) => {
    console.log(data);
});
