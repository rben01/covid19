import { dateStrParser, getFormatter } from "./utils.js";
const plotAesthetics = (() => {
    const width = 600, height = 600;
    const pa = {
        width: width,
        height: height,
        axis: {
            margins: {
                top: 3,
                bottom: 60,
                left: 40,
                right: 3,
            },
            width: null,
            height: null,
            style: {
                strokeWidth: 1,
                tickLength: 6,
                axisColor: "black",
                gridlineColor: "#e4e4e4",
                labelTranslateX: (7 / 600) * width,
                labelTranslateY: (7 / 600) * height,
            },
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
    const count = "net";
    const caseType = "cases";
    const svg = lineGraph
        .append("svg")
        .attr("width", plotAesthetics.width)
        .attr("height", plotAesthetics.height);
    const chartArea = svg.append("g").classed("line-chart-area", true);
    const { min_nonzero: _minDateStr, max: _maxDateStr } = allCovidData[location].agg.net.date;
    const { min_nonzero: minVal, max: maxVal } = allCovidData[location].agg[count][caseType];
    console.log(minVal, maxVal);
    const [minDate, maxDate] = [_minDateStr, _maxDateStr].map(dateStrParser);
    const xScale = d3
        .scaleTime()
        .domain([minDate, maxDate])
        .range([
        plotAesthetics.axis.margins.left,
        plotAesthetics.width - plotAesthetics.axis.margins.right,
    ]);
    const yScale = d3
        .scaleLog()
        .domain([minVal, maxVal])
        .range([plotAesthetics.axis.height, plotAesthetics.axis.margins.top]);
    const { strokeWidth, axisColor, tickLength, gridlineColor, } = plotAesthetics.axis.style;
    const xTicks = xScale.ticks(d3.timeDay.every(7));
    const yFormatter = getFormatter(count, caseType, 1);
    const yTicks = yScale.ticks(15);
    const xAxis = chartArea.append("g").classed("line-chart-x-axis", true);
    const yAxis = chartArea.append("g").classed("line-chart-y-axis", true);
    xAxis
        .selectAll()
        .data(xTicks)
        .join("line")
        .classed("x-axis-tick", true)
        .attr("x1", xScale)
        .attr("x2", xScale)
        .attr("y1", yScale(minVal))
        .attr("y2", yScale(minVal) + tickLength)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    yAxis
        .selectAll()
        .data(yTicks)
        .join("line")
        .classed("y-axis-tick", true)
        .attr("x1", xScale(minDate))
        .attr("x2", xScale(minDate) - plotAesthetics.axis.style.tickLength)
        .attr("y1", yScale)
        .attr("y2", yScale)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    xAxis
        .selectAll()
        .data(xTicks)
        .join("line")
        .classed("x-axis-gridline", true)
        .attr("x1", xScale)
        .attr("x2", xScale)
        .attr("y1", yScale(minVal))
        .attr("y2", yScale(maxVal))
        .attr("stroke", plotAesthetics.axis.style.gridlineColor)
        .attr("stroke-width", plotAesthetics.axis.style.strokeWidth);
    yAxis
        .selectAll()
        .data(yTicks)
        .join("line")
        .classed("y-axis-gridline", true)
        .attr("x1", xScale(minDate))
        .attr("x2", xScale(maxDate))
        .attr("y1", yScale)
        .attr("y2", yScale)
        .attr("stroke", plotAesthetics.axis.style.gridlineColor)
        .attr("stroke-width", plotAesthetics.axis.style.strokeWidth);
    xAxis
        .selectAll()
        .data(xTicks)
        .join("text")
        .classed("x-axis-label", true)
        .text((date) => {
        const dayOfMonth = date.getDate();
        if (dayOfMonth % 7 == 1 && dayOfMonth < 28) {
            return dateFormatter(date);
        }
        return "";
    })
        .attr("text-anchor", "end")
        .attr("font-size", "70%")
        .attr("transform", (d) => `translate(${xScale(d) + plotAesthetics.axis.style.labelTranslateX},${yScale(minVal) +
        tickLength +
        plotAesthetics.axis.style.labelTranslateY}) rotate(-60)`);
    yAxis
        .selectAll()
        .data(yTicks)
        .join("text")
        .classed("y-axis-label", true)
        .text((y) => {
        const firstDigit = +y.toString()[0];
        if (firstDigit <= 4 || firstDigit === 6) {
            return yFormatter(y);
        }
        return "";
    })
        .attr("x", xScale(minDate) - plotAesthetics.axis.style.tickLength - 3)
        .attr("y", yScale)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("font-size", "70%");
    xAxis
        .selectAll()
        .data([minDate, maxDate])
        .join("line")
        .classed("x-axis-axis", true)
        .attr("x1", xScale)
        .attr("x2", xScale)
        .attr("y1", yScale(minVal))
        .attr("y2", yScale(maxVal))
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    yAxis
        .selectAll()
        .data([minVal, maxVal])
        .join("line")
        .classed("y-axis-axis", true)
        .attr("x1", xScale(minDate))
        .attr("x2", xScale(maxDate))
        .attr("y1", yScale)
        .attr("y2", yScale)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
}
