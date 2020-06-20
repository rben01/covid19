import { dateStrParser, getFormatter } from "./utils.js";
const plotAesthetics = (() => {
    const pa = {
        width: 600,
        height: 600,
        axis: {
            margins: {
                bottom: 60,
                left: 30,
            },
            width: null,
            height: null,
        },
        colors: {
            scale: d3.schemeTableau10,
        },
    };
    pa.axis.width = pa.width - pa.axis.margins.left;
    pa.axis.height = pa.height - pa.axis.margins.bottom;
    return pa;
})();
const lineGraph = d3
    .select("#line-charts-section")
    .append("div")
    .attr("id", "line-chart");
function updateLineGraph(lineGraph, location, caseType, count, startFrom) { }
const dateFormatter = d3.timeFormat("%b %-d");
export function initializeLineGraph(allCovidData, geoCovidData) {
    lineGraph.datum({ allCovidData, geoCovidData });
    const location = "usa";
    const count = "dodd";
    const caseType = "cases";
    const { min_nonzero: minDate, max: maxDate } = allCovidData[location].agg.net.date;
    const xScale = d3
        .scaleTime()
        .domain([dateStrParser(minDate), dateStrParser(maxDate)])
        .range([plotAesthetics.axis.margins.left, plotAesthetics.width]);
    const xAxis = d3
        .axisBottom(xScale)
        .ticks(d3.timeDay.every(7))
        .tickFormat((date) => {
        const dayOfMonth = date.getDate();
        if (dayOfMonth % 7 == 1 && dayOfMonth < 28) {
            return dateFormatter(date);
        }
        return "";
    });
    const { min_nonzero: minVal, max: maxVal } = allCovidData[location].agg.net[caseType];
    const yScale = d3
        .scaleLog()
        .domain([minVal, maxVal])
        .range([plotAesthetics.axis.height, 0]);
    const yFormatter = getFormatter(count, caseType, 1);
    const yAxis = d3
        .axisLeft(yScale)
        .ticks(6)
        .tickFormat((n) => {
        const firstDigit = +`${n}`[0];
        if (firstDigit <= 4 || firstDigit % 2 === 0) {
            return yFormatter(n);
        }
        return "";
    });
    const svg = lineGraph
        .append("svg")
        .attr("width", plotAesthetics.width)
        .attr("height", plotAesthetics.height);
    const axesGroup = svg.append("g").classed("line-chart-axes", true);
    axesGroup
        .append("g")
        .classed("line-chart-x-axis", true)
        .attr("transform", `translate(0,${plotAesthetics.axis.height})`)
        .call(xAxis)
        .selectAll("text")
        .attr("text-anchor", "end")
        .attr("dx", "-8px")
        .attr("dy", "3px")
        .attr("transform", "rotate(-60)");
    axesGroup
        .append("g")
        .classed("line-chart-y-axis", true)
        .attr("transform", `translate(${plotAesthetics.axis.margins.left},0)`)
        .call(yAxis);
}
