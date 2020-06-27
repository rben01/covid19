import { dateStrParser, EPSILON, getFormatter, MS_PER_DAY } from "./utils.js";
class Line {
    constructor(feature) {
        this.feature = feature;
        this.points = [];
    }
    push(p) {
        this.points.push(p);
    }
}
const plotAesthetics = (() => {
    const chartWidth = 500, chartHeight = 500;
    const outerMargins = {
        top: 6,
        bottom: 100,
        left: 40,
        right: 3,
    };
    const fullWidth = chartWidth + outerMargins.left + outerMargins.right;
    const fullHeight = chartHeight + outerMargins.top + outerMargins.bottom;
    const scaleFactory = () => d3.scaleOrdinal().range(d3.schemeTableau10);
    const pa = {
        fullWidth,
        fullHeight,
        graph: {
            outerMargins,
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
            __scaleFactory: scaleFactory,
            __scale: scaleFactory(),
            resetTo: function (features) {
                this.__scale = this.__scaleFactory();
                features.forEach(f => this.scale(f));
            },
            scale: function (f) {
                return this.__scale(f.properties.code);
            },
        },
    };
    return pa;
})();
const dateFormatter = d3.timeFormat("%b %-d");
export function initializeLineGraph(allCovidData, allGeoData) {
    const location = "usa";
    const count = "dodd";
    const affliction = "cases";
    const accumulation = "per_capita";
    const startFrom = "first_date";
    const startIndex = 0;
    const datum = {
        allCovidData,
        allGeoData,
        location,
        count,
        affliction,
        accumulation,
        startFrom,
        startIndex,
    };
    const lineGraphContainer = d3
        .select("#line-charts-section")
        .append("div");
    lineGraphContainer.datum(datum);
    const checkboxGroup = lineGraphContainer
        .append("div")
        .classed("checkbox-table", true);
    lineGraphContainer
        .append("div")
        .classed("line-chart-disclaimer", true)
        .append("span")
        .text("* 7-day moving average");
    const checkboxTable = checkboxGroup.append("table");
    checkboxTable
        .append("tr")
        .selectAll()
        .data(["Location", "Count", "Cases/Deaths", "Per 100k/Total"])
        .join("th")
        .text((d) => d)
        .attr("colspan", 2);
    const rows = [
        [
            { key: "location", value: "usa", name: "USA" },
            { key: "count", value: "dodd", name: "Daily Increase*" },
            { key: "affliction", value: "cases", name: "Cases" },
            { key: "accumulation", value: "per_capita", name: "Per 100k Residents" },
        ],
        [
            { key: "location", value: "world", name: "World" },
            { key: "count", value: "net", name: "Cases Over Time" },
            { key: "affliction", value: "deaths", name: "Deaths" },
            { key: "accumulation", value: "total", name: "Total for Location" },
        ],
    ];
    for (const row of rows) {
        const tr = checkboxTable.append("tr");
        for (const col of row) {
            const { key, value, name } = col;
            tr.append("td").text(name);
            tr.append("td")
                .append("input")
                .property("checked", value === datum[key])
                .attr("type", "radio")
                .property("name", `${key}-line-chart`)
                .on("change", function (d) {
                const datum = lineGraphContainer.datum();
                datum[key] = value;
                updateLineGraph(lineGraphContainer, 7, { refreshColors: true });
            });
        }
    }
    const lineGraph = lineGraphContainer.append("div").classed("line-chart", true);
    const svg = lineGraph
        .append("svg")
        .attr("width", plotAesthetics.fullWidth)
        .attr("height", plotAesthetics.fullHeight);
    const chartArea = svg.append("g").classed("line-chart-area", true);
    chartArea.append("g").classed("line-chart-x-axis", true);
    chartArea.append("g").classed("line-chart-y-axis", true);
    const legendContainer = lineGraphContainer
        .append("div")
        .classed("line-chart-legend-container", true);
    legendContainer
        .append("div")
        .classed("line-chart-legend-button-container", true)
        .append("span")
        .selectAll()
        .data([-10, -1, 1, 10])
        .join("button")
        .classed("line-chart-legend-button", true)
        .html((n) => {
        if (n == -10) {
            return '<i class="fas fa-angle-double-up"></i>';
        }
        else if (n == -1) {
            return '<i class="fas fa-chevron-up"></i>';
        }
        else if (n == 1) {
            return '<i class="fas fa-chevron-down"></i>';
        }
        else if (n === 10) {
            return '<i class="fas fa-angle-double-down"></i>';
        }
        else {
            throw new Error(`Unexpected value ${n}`);
        }
    })
        .on("click", function (n) {
        lineGraphContainer.datum().startIndex += n;
        updateLineGraph(lineGraphContainer, 7, { refreshColors: false });
    });
    legendContainer
        .append("table")
        .classed("line-chart-legend", true)
        .append("tr")
        .append("th")
        .attr("colspan", 4);
    updateLineGraph(lineGraphContainer, 7);
}
function updateLineGraph(lineGraphContainer, smoothAvgDays, { refreshColors } = { refreshColors: false }) {
    const _datum = lineGraphContainer.datum();
    const { location, count, affliction, accumulation, allGeoData, startFrom } = _datum;
    let startIndex = _datum.startIndex;
    const lineGraph = lineGraphContainer.selectAll(".line-chart");
    const scopedGeoData = allGeoData[location];
    const nLines = 10;
    startIndex = Math.max(0, Math.min(startIndex, scopedGeoData.features.length - nLines - 1));
    _datum.startIndex = startIndex;
    const caseType = (accumulation === "per_capita"
        ? `${affliction}_per_capita`
        : affliction);
    const sortedFeatures = [...scopedGeoData.features]
        .filter(f => typeof f.covidData !== "undefined")
        .sort((f1, f2) => {
        const currentMovingAvg = (feature) => {
            const values = feature.covidData[count][caseType];
            return values
                .slice(values.length - smoothAvgDays)
                .reduce((a, b) => a + b);
        };
        const y1 = currentMovingAvg(f1);
        const y2 = currentMovingAvg(f2);
        return y2 - y1;
    });
    if (refreshColors) {
        plotAesthetics.colors.resetTo(sortedFeatures);
    }
    const topNPlaces = sortedFeatures.slice(startIndex, startIndex + nLines);
    const lines = [];
    if (startFrom === "first_date") {
        for (const feature of topNPlaces) {
            const thisLine = new Line(feature);
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
        for (const feature of topNPlaces) {
            const thisLine = new Line(feature);
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
    lines.sort((l1, l2) => l2.points[l2.points.length - 1].y - l1.points[l1.points.length - 1].y);
    const [minYVal, maxYVal] = (() => {
        let min = Infinity, max = -Infinity;
        for (let line of lines) {
            for (let point of line.points) {
                const y = point.y;
                if (EPSILON < y && y < min) {
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
                .reduce((a, b) => (a < b && a > EPSILON ? a : b));
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
    const yFormatter = getFormatter(count, caseType, smoothAvgDays);
    const yTicks = axisYScale.ticks(15);
    const chartArea = lineGraph.selectAll(".line-chart-area");
    const xAxis = chartArea.selectAll(".line-chart-x-axis");
    const yAxis = chartArea.selectAll(".line-chart-y-axis");
    xAxis
        .selectAll(".x-axis-tick")
        .data(xTicks)
        .join((enter) => enter
        .append("line")
        .classed("x-axis-tick", true)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth), (update) => update, (exit) => exit.remove())
        .attr("x1", lineXScale)
        .attr("x2", lineXScale)
        .attr("y1", axisYScale(minYVal))
        .attr("y2", axisYScale(minYVal) + tickLength);
    yAxis
        .selectAll(".y-axis-tick")
        .data(yTicks)
        .join((enter) => enter
        .append("line")
        .classed("y-axis-tick", true)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth), (update) => update, (exit) => exit.remove())
        .attr("x1", axisXScale(minXVal))
        .attr("x2", axisXScale(minXVal) - plotAesthetics.graph.axisStyle.tickLength)
        .attr("y1", lineYScale)
        .attr("y2", lineYScale);
    xAxis
        .selectAll(".x-axis-gridline")
        .data(xTicks)
        .join((enter) => enter
        .append("line")
        .classed("x-axis-gridline", true)
        .attr("stroke", gridlineColor)
        .attr("stroke-width", strokeWidth), (update) => update, (exit) => exit.remove())
        .attr("x1", lineXScale)
        .attr("x2", lineXScale)
        .attr("y1", axisYScale(minYVal))
        .attr("y2", axisYScale(maxYVal));
    yAxis
        .selectAll(".y-axis-gridline")
        .data(yTicks)
        .join((enter) => enter
        .append("line")
        .classed("y-axis-gridline", true)
        .attr("stroke", plotAesthetics.graph.axisStyle.gridlineColor)
        .attr("stroke-width", plotAesthetics.graph.axisStyle.strokeWidth), (update) => update, (exit) => exit.remove())
        .attr("x1", axisXScale(minXVal))
        .attr("x2", axisXScale(maxXVal))
        .attr("y1", lineYScale)
        .attr("y2", lineYScale);
    const xTickLabels = xAxis
        .selectAll(".x-axis-label")
        .data(xTicks)
        .join((enter) => enter
        .append("text")
        .classed("x-axis-label", true)
        .attr("font-size", "70%"), (update) => update, (exit) => exit.remove());
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
        .selectAll(".y-axis-label")
        .data(yTicks)
        .join((enter) => enter
        .append("text")
        .classed("y-axis-label", true)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("font-size", "70%"), (update) => update, (exit) => exit.remove())
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
        .attr("y", lineYScale);
    const pathDrawer = d3
        .line()
        .x((p) => lineXScale(p.x))
        .y((p) => lineYScale(p.y))
        .defined((p) => p.y > EPSILON)
        .curve(d3.curveMonotoneX);
    chartArea
        .selectAll(".chart-line")
        .data(lines)
        .join((enter) => enter
        .append("path")
        .classed("chart-line", true)
        .attr("stroke-width", plotAesthetics.graph.line.strokeWidth)
        .attr("fill-opacity", 0), (update) => update, (exit) => exit.remove())
        .attr("d", (l) => pathDrawer(l.points))
        .attr("stroke", (l) => plotAesthetics.colors.scale(l.feature));
    const legend = lineGraphContainer.selectAll(".line-chart-legend");
    function getInfoFromXVal(x) {
        let xVal, xStr;
        if (startFrom === "first_date") {
            x = x;
            const roundedXVal = new Date(Math.round(x.getTime() / MS_PER_DAY) * MS_PER_DAY);
            const year = roundedXVal.getUTCFullYear();
            const month = roundedXVal.getUTCMonth();
            const date = roundedXVal.getUTCDate();
            xVal = new Date(year, month, date);
            if (xVal < minXVal) {
                xVal = minXVal;
            }
            else if (xVal > maxXVal) {
                xVal = maxXVal;
            }
            xStr = dateFormatter(xVal);
        }
        else {
            x = x;
            xVal = Math.round(x);
            if (xVal < minXVal) {
                xVal = minXVal;
            }
            else if (xVal > maxXVal) {
                xVal = maxXVal;
            }
            xStr = `${xVal} days since`;
        }
        return { xVal, xStr };
    }
    const mainChartArea = chartArea.append("g");
    mainChartArea
        .selectAll(".chart-region")
        .data([
        {
            x: axisXScale(minXVal),
            y: axisYScale(maxYVal),
            width: axisXScale(maxXVal) - axisXScale(minXVal),
            height: axisYScale(minYVal) - axisYScale(maxYVal),
        },
    ])
        .join("rect")
        .classed("chart-region", true)
        .attr("x", (d) => d.x)
        .attr("y", (d) => d.y)
        .attr("width", (d) => d.width)
        .attr("height", (d) => d.height)
        .attr("fill-opacity", 0)
        .attr("stroke", axisColor)
        .attr("stroke-width", strokeWidth)
        .on("mousemove", function () {
        const mouseXScreen = d3.mouse(this)[0];
        const mouseXVal = lineXScale.invert(mouseXScreen);
        const { xVal, xStr: headerStr } = getInfoFromXVal(mouseXVal);
        const values = lines.map(line => {
            const points = line.points;
            let left = 0, right = points.length - 1;
            while (left < right - 1) {
                const middle = Math.floor((left + right) / 2);
                const thisX = points[middle].x;
                if (xVal === thisX) {
                    return points[middle].y;
                }
                else if (xVal < points[middle].x) {
                    right = middle;
                }
                else {
                    left = middle;
                }
            }
            const [leftDist, rightDist] = startFrom === "first_date"
                ? [left, right].map(i => Math.abs(points[i].x.getTime() -
                    xVal.getTime()))
                : [left, right].map(i => Math.abs(points[i].x - xVal));
            if (leftDist < rightDist) {
                return points[left].y;
            }
            else {
                return points[right].y;
            }
        });
        legend
            .selectAll("td .legend-value")
            .text((_, i) => yFormatter(values[i]));
        legend.selectAll("tr th").text(headerStr);
        const hoverLineX = lineXScale(xVal);
        mainChartArea
            .selectAll(".line-chart-hover-line")
            .data([0])
            .join((enter) => enter
            .insert("line", "rect.chart-region")
            .classed("line-chart-hover-line", true)
            .attr("stroke", "#444")
            .attr("stroke-width", 1.5)
            .attr("stroke-dasharray", "4 4"))
            .attr("x1", hoverLineX)
            .attr("x2", hoverLineX)
            .attr("y1", axisYScale(minYVal))
            .attr("y2", axisYScale(maxYVal));
    })
        .on("mouseout", function () {
        const values = lines.map(line => line.points[line.points.length - 1].y);
        const headerStr = getInfoFromXVal(maxXVal).xStr;
        legend.selectAll("tr th").text(headerStr);
        legend
            .selectAll("td .legend-value")
            .text((_, i) => yFormatter(values[i]));
        mainChartArea.selectAll(".line-chart-hover-line").remove();
    });
    const headerStr = getInfoFromXVal(maxXVal).xStr;
    legend.selectAll("tr th").text(headerStr);
    legend
        .selectAll("tr.legend-data-row")
        .data(lines)
        .join("tr")
        .classed("legend-data-row", true)
        .each(function (line, index) {
        const row = d3.select(this);
        const rowData = [
            { type: "index", datum: `${startIndex + index + 1}.` },
            { type: "color", datum: plotAesthetics.colors.scale(line.feature) },
            { type: "name", datum: line.feature.properties.name },
            {
                type: "number",
                datum: yFormatter(line.points[line.points.length - 1].y),
            },
        ];
        row.selectAll("td")
            .data(rowData)
            .join("td")
            .classed("color-cell", true)
            .each(function (d) {
            const legendItemClass = "legend-item";
            let cellClass, _baseEnterFunc, updateFunc;
            if (d.type === "color") {
                cellClass = "legend-color-square";
                _baseEnterFunc = (enter) => enter.append("div");
                updateFunc = (update) => update.style("background-color", (c) => c);
            }
            else if (d.type === "index") {
                cellClass = "legend-index";
                _baseEnterFunc = (enter) => enter.append("span");
                updateFunc = (update) => update.text((t) => t);
            }
            else if (d.type === "name") {
                cellClass = "legend-label";
                _baseEnterFunc = (enter) => enter.append("span");
                updateFunc = (update) => update.text((t) => t);
            }
            else if (d.type === "number") {
                cellClass = "legend-value";
                _baseEnterFunc = (enter) => enter.append("span");
                updateFunc = (update) => update.text((t) => t);
            }
            else {
                throw new Error(`Unexpected type in ${d}`);
            }
            const enterFunc = (enter) => _baseEnterFunc(enter)
                .classed(cellClass, true)
                .classed(legendItemClass, true);
            const td = d3.select(this);
            td.selectAll(`.${cellClass}`)
                .data([d.datum])
                .join(enterFunc)
                .call(updateFunc);
        });
    });
}
