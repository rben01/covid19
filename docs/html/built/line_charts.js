import { dateStrParser, getFormatter } from "./utils.js";
class Line {
    constructor(name) {
        this.name = name;
        this.points = [];
    }
    push(p) {
        this.points.push(p);
    }
}
const plotAesthetics = (() => {
    const chartWidth = 500, chartHeight = 500;
    const outerMargins = {
        top: 3,
        bottom: 60,
        left: 40,
        right: 3,
    };
    const legend = {
        width: 90,
    };
    const fullWidth = chartWidth + outerMargins.left + outerMargins.right + legend.width;
    const fullHeight = chartHeight + outerMargins.top + outerMargins.bottom;
    const pa = {
        fullWidth,
        fullHeight,
        graph: {
            outerMargins,
            legend,
            innerMargin: 15,
            width: chartWidth,
            height: chartHeight,
            axisStyle: {
                strokeWidth: 1,
                tickLength: 6,
                axisColor: "black",
                gridlineColor: "#e4e4e4",
                labelTranslateX: (7 / 500) * chartWidth,
                labelTranslateY: (7 / 500) * chartHeight,
            },
            line: {
                strokeWidth: 2,
            },
        },
        colors: {
            scale: d3.scaleOrdinal().range(d3.schemeTableau10),
        },
    };
    pa.graph.width = pa.fullWidth - pa.graph.outerMargins.left;
    pa.graph.height = pa.fullHeight - pa.graph.outerMargins.bottom;
    return pa;
})();
const lineGraph = d3.select("#line-charts-section").append("div").attr("id", "line-chart");
const dateFormatter = d3.timeFormat("%b %-d");
const svg = lineGraph
    .append("svg")
    .attr("width", plotAesthetics.fullWidth)
    .attr("height", plotAesthetics.fullHeight);
const chartArea = svg.append("g").classed("line-chart-area", true);
export function initializeLineGraph(allCovidData, allGeoData) {
    lineGraph.datum({ allCovidData, allGeoData });
    const location = "usa";
    const count = "dodd";
    const caseType = "deaths";
    updateLineGraph(location, caseType, count, "first_date", 1);
}
function updateLineGraph(location, caseType, count, startFrom, smoothAvgDays) {
    const allGeoData = lineGraph.datum().allGeoData;
    const scopedGeoData = allGeoData[location];
    const nLines = 10;
    const lines = [];
    const topNPlaces = [];
    let cutoffValue = -Infinity;
    for (const feature of scopedGeoData.features) {
        if (typeof feature.covidData === "undefined") {
            continue;
        }
        const values = feature.covidData[count][caseType];
        const currentValue = values[values.length - 1];
        if (topNPlaces.length < nLines) {
            topNPlaces.push([feature, currentValue]);
            if (currentValue < cutoffValue) {
                cutoffValue = currentValue;
            }
        }
        else if (currentValue > cutoffValue) {
            const idxToReplace = topNPlaces.findIndex(([_, value]) => value === cutoffValue);
            topNPlaces[idxToReplace] = [feature, currentValue];
            cutoffValue = Math.min(...topNPlaces.map(([_, value]) => value));
        }
    }
    if (startFrom === "first_date") {
        for (const [feature, _] of topNPlaces) {
            const thisLine = new Line(feature.properties.name);
            const covidData = feature.covidData;
            const dates = Object.keys(covidData.date).sort();
            const values = covidData[count][caseType];
            if (count === "dodd" && smoothAvgDays >= 2) {
                let sum = values.slice(0, smoothAvgDays - 1).reduce((a, b) => a + b);
                let prevValue = 0;
                for (let i = smoothAvgDays; i < values.length; ++i) {
                    const dateStr = dates[i];
                    const value = values[i];
                    sum -= prevValue;
                    sum += value;
                    prevValue = values[i - smoothAvgDays + 1];
                    const avg = sum / smoothAvgDays;
                    thisLine.push({
                        x: dateStrParser(dateStr),
                        y: avg,
                    });
                }
            }
            else {
                for (let i = 0; i < dates.length; ++i) {
                    const dateStr = dates[i];
                    const value = values[i];
                    thisLine.push({
                        x: dateStrParser(dateStr),
                        y: value,
                    });
                }
            }
            lines.push(thisLine);
        }
    }
    else {
        for (const [feature, _] of topNPlaces) {
            const thisLine = new Line(feature.properties.name);
            const covidData = feature.covidData;
            const values = covidData[count][caseType];
            const startIndex = covidData.outbreak_cutoffs[caseType];
            if (count === "dodd" && smoothAvgDays >= 2) {
                let sum = values
                    .slice(startIndex, startIndex + smoothAvgDays - 1)
                    .reduce((a, b) => a + b);
                let prevValue = 0;
                for (let i = Math.max(startIndex, smoothAvgDays); i < values.length; ++i) {
                    const value = values[i];
                    sum -= prevValue;
                    sum += value;
                    prevValue = values[i - smoothAvgDays + 1];
                    const avg = sum / smoothAvgDays;
                    thisLine.push({
                        x: i,
                        y: avg,
                    });
                }
            }
            else {
                for (let i = startIndex; i < values.length; ++i) {
                    const value = values[i];
                    thisLine.push({ x: i, y: value });
                }
            }
            lines.push(thisLine);
        }
    }
    const [minYVal, maxYVal] = (() => {
        let min = Infinity, max = -Infinity;
        for (let line of lines) {
            for (let point of line.points) {
                const y = point.y;
                if (0 < y && y < min) {
                    min = y;
                }
                else if (y > max) {
                    max = y;
                }
            }
        }
        return [min, max];
    })();
    const innerMargin = plotAesthetics.graph.innerMargin;
    const axisYScale = d3
        .scaleLog()
        .domain([minYVal, maxYVal])
        .range([plotAesthetics.graph.height, plotAesthetics.graph.outerMargins.top]);
    const lineYScale = d3
        .scaleLog()
        .domain([minYVal, maxYVal])
        .range([
        plotAesthetics.graph.height - innerMargin,
        plotAesthetics.graph.outerMargins.top + innerMargin,
    ]);
    const { axisXScale, lineXScale, minXVal, maxXVal, } = (() => {
        const axisRange = [
            plotAesthetics.graph.outerMargins.left,
            plotAesthetics.fullWidth - plotAesthetics.graph.outerMargins.right,
        ];
        const lineRange = [axisRange[0] + innerMargin, axisRange[1] - innerMargin];
        if (startFrom === "first_date") {
            const lineXs = lines.map(line => line.points.map(p => p.x));
            const minDate = lineXs
                .map(points => points[0])
                .reduce((a, b) => (a < b ? a : b));
            const maxDate = lineXs
                .map(points => points[points.length - 1])
                .reduce((a, b) => (a > b ? a : b));
            return {
                axisXScale: d3.scaleTime().domain([minDate, maxDate]).range(axisRange),
                lineXScale: d3.scaleTime().domain([minDate, maxDate]).range(lineRange),
                minXVal: minDate,
                maxXVal: maxDate,
            };
        }
        else {
            const minXVal = 0;
            const maxXVal = Math.max(...lines.map(line => line.points[line.points.length - 1].x));
            return {
                axisXScale: d3
                    .scaleLinear()
                    .domain([minXVal, maxXVal])
                    .range(axisRange),
                lineXScale: d3
                    .scaleLinear()
                    .domain([minXVal, maxXVal])
                    .range(lineRange),
                minXVal: minXVal,
                maxXVal: maxXVal,
            };
        }
    })();
    const { strokeWidth, axisColor, tickLength, gridlineColor, } = plotAesthetics.graph.axisStyle;
    const xTicks = startFrom === "first_date"
        ? axisXScale.ticks(d3.timeDay.every(7))
        : axisXScale.ticks(10);
    const yFormatter = getFormatter(count, caseType, 1);
    const yTicks = axisYScale.ticks(15);
    const xAxis = chartArea.append("g").classed("line-chart-x-axis", true);
    const yAxis = chartArea.append("g").classed("line-chart-y-axis", true);
    xAxis
        .selectAll()
        .data(xTicks)
        .join("line")
        .classed("x-axis-tick", true)
        .attr("x1", lineXScale)
        .attr("x2", lineXScale)
        .attr("y1", axisYScale(minYVal))
        .attr("y2", axisYScale(minYVal) + tickLength)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    yAxis
        .selectAll()
        .data(yTicks)
        .join("line")
        .classed("y-axis-tick", true)
        .attr("x1", axisXScale(minXVal))
        .attr("x2", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength)
        .attr("y1", lineYScale)
        .attr("y2", lineYScale)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    xAxis
        .selectAll()
        .data(xTicks)
        .join("line")
        .classed("x-axis-gridline", true)
        .attr("x1", lineXScale)
        .attr("x2", lineXScale)
        .attr("y1", axisYScale(minYVal))
        .attr("y2", axisYScale(maxYVal))
        .attr("stroke", gridlineColor)
        .attr("stroke-width", strokeWidth);
    yAxis
        .selectAll()
        .data(yTicks)
        .join("line")
        .classed("y-axis-gridline", true)
        .attr("x1", axisXScale(minXVal))
        .attr("x2", axisXScale(maxXVal))
        .attr("y1", lineYScale)
        .attr("y2", lineYScale)
        .attr("stroke", plotAesthetics.graph.axisStyle.gridlineColor)
        .attr("stroke-width", plotAesthetics.graph.axisStyle.strokeWidth);
    const xTickLabels = xAxis
        .selectAll()
        .data(xTicks)
        .join("text")
        .classed("x-axis-label", true)
        .attr("font-size", "70%");
    if (startFrom === "first_date") {
        xTickLabels
            .text((date) => {
            const dayOfMonth = date.getDate();
            return dayOfMonth % 7 == 1 && dayOfMonth < 28
                ? dateFormatter(date)
                : "";
        })
            .attr("transform", (d) => `translate(${lineXScale(d) + plotAesthetics.graph.axisStyle.labelTranslateX},${axisYScale(minYVal) +
            tickLength +
            plotAesthetics.graph.axisStyle.labelTranslateY}) rotate(-60)`)
            .attr("text-anchor", "end");
    }
    else {
        xTickLabels
            .text((daysSince) => {
            return daysSince % 5 == 0 ? daysSince : "";
        })
            .attr("transform", (daysSince) => `translate(${lineXScale(daysSince)},${axisYScale(minYVal) + tickLength + 13})`)
            .attr("text-anchor", "middle");
    }
    yAxis
        .selectAll()
        .data(yTicks)
        .join("text")
        .classed("y-axis-label", true)
        .text((y) => {
        const yStr = yFormatter(y);
        const firstSigFigIndex = yStr.search(/[1-9]/);
        const firstSigFig = +yStr[firstSigFigIndex];
        if (firstSigFig <= 4 || firstSigFig === 6) {
            return yFormatter(y);
        }
        return "";
    })
        .attr("x", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength - 3)
        .attr("y", lineYScale)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("font-size", "70%");
    const axisLine = d3
        .line()
        .x((p) => axisXScale(p[0]))
        .y((p) => axisYScale(p[1]));
    chartArea
        .selectAll()
        .data([
        [
            [minXVal, minYVal],
            [minXVal, maxYVal],
            [maxXVal, maxYVal],
            [maxXVal, minYVal],
            [minXVal, minYVal],
        ],
    ])
        .join("path")
        .attr("d", axisLine)
        .attr("fill-opacity", 0)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth);
    const pathDrawer = d3
        .line()
        .x((p) => lineXScale(p.x))
        .y((p) => lineYScale(p.y))
        .defined((p) => lineYScale(p.y) > 0);
    console.log(lines);
    chartArea
        .selectAll()
        .data(lines)
        .join("path")
        .attr("d", (l) => pathDrawer(l.points))
        .attr("stroke-width", plotAesthetics.graph.line.strokeWidth)
        .attr("fill-opacity", 0)
        .attr("stroke", (l) => plotAesthetics.colors.scale(l.name))
        .attr("_name", (l) => l.name);
}
