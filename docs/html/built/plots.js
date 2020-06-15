const MS_PER_DAY = 86400 * 1000;
const plotAesthetics = Object.freeze({
    width: { usa: 500, world: 600 },
    height: { usa: 350, world: 400 },
    colors: {
        scale: (t) => d3.interpolateCividis(1 - t),
        nSteps: 101,
        missing: "#ccc",
        zero: "#ddc",
    },
    legend: {
        padLeft: 20,
        barWidth: 15,
        padRight: 40,
        height: 275,
        gradientID: "verticalLegendGradient",
    },
    title: {
        height: 40,
    },
    get mapWidth() {
        const legend = this.legend;
        const mw = {};
        Object.keys(this.width).forEach((scope) => {
            const width = this.width[scope];
            mw[scope] = width - (legend.padLeft + legend.barWidth + legend.padRight);
        });
        return mw;
    },
});
function isPerCapita(caseType) {
    return caseType === "cases_per_capita" || caseType === "deaths_per_capita";
}
const dateStrParser = d3.timeParse("%Y-%m-%d");
const dateFormatter = d3.timeFormat("%Y-%m-%d");
function getDateNDaysAfter(startDate, n) {
    return dateFormatter(new Date(dateStrParser(startDate).getTime() + n * MS_PER_DAY));
}
function assignData({ allCovidData, allGeoData, }) {
    ["usa", "world"].forEach(key => {
        const scopedGeoData = allGeoData[key];
        scopedGeoData.features.forEach(feature => {
            feature.covidData = allCovidData[key].data[feature.properties.code];
        });
    });
}
function updateMaps({ plotGroup, date, dateIndex, }) {
    const minDate = plotGroup.datum().scopedCovidData.agg.date.min_nonzero;
    if (typeof dateIndex === "undefined") {
        dateIndex = Math.round((dateStrParser(date).getTime() - dateStrParser(minDate).getTime()) /
            MS_PER_DAY);
    }
    plotGroup.selectAll(".date-slider").property("value", dateIndex);
    const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(date));
    plotGroup.selectAll(".date-span").text(dateStr);
    plotGroup
        .selectAll(".plot-container")
        .each(function ({ caseType, vmin, vmax, }) {
        const plotContainer = d3.select(this);
        const formatter = isPerCapita(caseType)
            ? numberFormatters.float
            : numberFormatters.int;
        const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);
        const svg = plotContainer.selectAll("svg");
        svg.selectAll("path")
            .attr("fill", (d) => {
            if (typeof d.covidData === "undefined") {
                return plotAesthetics.colors.missing;
            }
            const index = d.covidData.date[date];
            if (typeof index === "undefined") {
                return plotAesthetics.colors.missing;
            }
            const value = d.covidData[caseType][index];
            if (value < vmin) {
                return plotAesthetics.colors.zero;
            }
            return plotAesthetics.colors.scale(colorScale(value));
        })
            .on("mouseover", (d) => {
            const noDataStr = "~No data~";
            const caseCount = (() => {
                if (typeof d.covidData === "undefined") {
                    return noDataStr;
                }
                const index = d.covidData.date[date];
                if (typeof index === "undefined") {
                    return noDataStr;
                }
                return formatter(d.covidData[caseType][index]);
            })();
            tooltip.html(`${date}<br>${d.properties.name}<br>${caseCount}`);
            return tooltip.style("visibility", "visible");
        })
            .on("mousemove", () => tooltip
            .style("top", `${+d3.event.pageY - 30}px`)
            .style("left", `${+d3.event.pageX + 10}px`))
            .on("mouseout", () => tooltip.style("visibility", "hidden"));
    });
}
const numberFormatters = { int: d3.format(",~r"), float: d3.format(",.2f") };
const tooltip = d3.select("body").append("div").attr("id", "tooltip");
function initializeChoropleth({ plotGroup, allCovidData, allGeoData, }) {
    const scope = plotGroup.datum().scope;
    const scopedCovidData = allCovidData[scope];
    const scopedGeoData = allGeoData[scope];
    plotGroup.datum({ ...plotGroup.datum(), scopedCovidData });
    const legendTransX = plotAesthetics.mapWidth[scope] + plotAesthetics.legend.padLeft;
    const legendTransY = (plotAesthetics.title.height +
        plotAesthetics.height[scope] -
        plotAesthetics.legend.height) /
        2;
    const { min_nonzero: minDate, max: maxDate } = scopedCovidData.agg.date;
    const firstDay = dateStrParser(minDate);
    const lastDay = dateStrParser(maxDate);
    const daysElapsed = Math.round((lastDay - firstDay) / MS_PER_DAY);
    plotGroup.selectAll(".plot-container").each(function () {
        const plotContainer = d3.select(this);
        const caseType = plotContainer.datum().caseType;
        const svg = plotContainer.selectAll("svg");
        const projection = (scope === "usa"
            ? d3.geoAlbersUsa()
            : d3.geoNaturalEarth1()).fitExtent([
            [0, plotAesthetics.title.height],
            [plotAesthetics.mapWidth[scope], plotAesthetics.height[scope]],
        ], scopedGeoData);
        const path = d3.geoPath(projection);
        svg.selectAll("path")
            .data(scopedGeoData.features)
            .join("path")
            .attr("d", path)
            .attr("stroke", "#fff8")
            .attr("stroke-width", 1);
        const legend = svg
            .append("g")
            .attr("transform", `translate(${legendTransX},${legendTransY})`);
        const { barWidth, height: barHeight } = plotAesthetics.legend;
        legend
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", barWidth)
            .attr("height", barHeight)
            .attr("fill", `url(#${plotAesthetics.legend.gradientID})`);
        const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[caseType];
        plotContainer.datum({ ...plotContainer.datum(), vmin, vmax });
        const legendScale = d3
            .scaleLog()
            .nice()
            .base(10)
            .domain([vmin, vmax])
            .range([barHeight, 0]);
        legendScale.ticks(8).forEach((y) => {
            const ys = legendScale(y);
            legend
                .append("line")
                .attr("x1", (barWidth * 2) / 3)
                .attr("x2", barWidth)
                .attr("y1", ys)
                .attr("y2", ys)
                .attr("stroke", "white")
                .attr("stroke-width", 1);
        });
        const fmtStr = isPerCapita(caseType) ? "~g" : "~s";
        const tickFormatter = legendScale.tickFormat(7, fmtStr);
        legendScale.ticks(7).forEach((y) => {
            legend
                .append("text")
                .attr("x", barWidth + 4)
                .attr("y", legendScale(y))
                .text(`${tickFormatter(y)}`)
                .attr("fill", "black")
                .attr("font-size", 12)
                .attr("font-family", "sans-serif")
                .attr("text-anchor", "left")
                .attr("alignment-baseline", "middle");
        });
        let caseTypeStr = caseType;
        let suffixStr = "";
        if (isPerCapita(caseTypeStr)) {
            caseTypeStr = caseTypeStr.replace("_per_capita", "");
            suffixStr = " Per 100,000 People";
        }
        caseTypeStr = caseTypeStr.replace(/^./, (c) => c.toUpperCase());
        const titleStr = `Total ${caseTypeStr}${suffixStr}`;
        svg.append("text")
            .attr("x", 20)
            .attr("y", plotAesthetics.title.height)
            .attr("text-anchor", "left")
            .attr("alignment-baseline", "top")
            .text(titleStr)
            .attr("font-size", 24)
            .attr("font-family", "sans-serif")
            .attr("fill", "black");
        plotContainer.selectAll(".date-slider").each(function () {
            this.min = 0;
            this.max = daysElapsed;
            this.step = 1;
            this.value = daysElapsed;
        });
    });
    updateMaps({ plotGroup, date: maxDate, dateIndex: daysElapsed });
}
const plotGroups = d3
    .select("#content")
    .selectAll()
    .data([{ scope: "usa" }, { scope: "world" }])
    .join("div")
    .classed("plot-scope-group", true);
const plotDivs = plotGroups
    .selectAll()
    .data(({ scope }) => {
    const data = [];
    ["cases", "cases_per_capita", "deaths", "deaths_per_capita"].forEach((caseType) => {
        data.push({ scope, caseType });
    });
    return data;
})
    .join("div")
    .classed("plot-container", true);
const svgs = plotDivs
    .append("svg")
    .attr("width", (d) => plotAesthetics.width[d.scope])
    .attr("height", (d) => plotAesthetics.height[d.scope]);
const sliderRow = plotDivs.append("div").append("span");
const sliders = sliderRow
    .append("input")
    .classed("date-slider", true)
    .attr("type", "range")
    .attr("min", 0)
    .attr("max", 1)
    .property("value", 1)
    .on("input", function (d) {
    const plotGroup = plotGroups.filter((p) => p.scope === d.scope);
    const dateIndex = +this.value;
    const minDate = plotGroup.datum().scopedCovidData.agg.date.min_nonzero;
    const date = getDateNDaysAfter(minDate, dateIndex);
    updateMaps({ plotGroup, date, dateIndex });
});
const dateSpans = sliderRow.append("span").classed("date-span", true);
const buttonsRow = plotDivs.append("div").append("span");
buttonsRow.append("button").classed("play-button", true);
// Create gradient
(() => {
    const defs = svgs.append("defs");
    const verticalLegendGradient = defs
        .append("linearGradient")
        .attr("id", plotAesthetics.legend.gradientID)
        .attr("x1", "0%")
        .attr("x2", "0%")
        .attr("y1", "100%")
        .attr("y2", "0%");
    d3.range(plotAesthetics.colors.nSteps).forEach((i) => {
        const percent = (100 * i) / (plotAesthetics.colors.nSteps - 1);
        const proptn = percent / 100;
        verticalLegendGradient
            .append("stop")
            .attr("offset", `${percent}%`)
            .attr("stop-color", plotAesthetics.colors.scale(proptn))
            .attr("stop-opacity", 1);
    });
})();
const nowMS = new Date().getTime();
Promise.all([
    d3.json(`https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/covid_data.json?t=${nowMS}`),
    d3.json("https://raw.githubusercontent.com/rben01/covid19/js-migrate/docs/data/geo_data.json"),
    ,
]).then(objects => {
    const allCovidData = objects[0];
    const allGeoData = objects[1];
    assignData({ allCovidData, allGeoData });
    plotGroups.each(function () {
        const plotGroup = d3.select(this);
        initializeChoropleth({
            plotGroup,
            allCovidData,
            allGeoData,
        });
    });
});
