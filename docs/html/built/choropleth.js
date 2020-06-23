import { SCOPES, } from "./types.js";
import { dateStrParser, isPerCapita } from "./utils.js";
const MS_PER_DAY = 86400 * 1000;
const plotAesthetics = Object.freeze((() => {
    const pa = {
        width: { usa: 500, world: 500 },
        height: { usa: 325, world: 300 },
        colors: {
            scale: (t) => d3.interpolateCividis(1 - t),
            nSteps: 101,
            missing: "#bbb",
            zero: "#ddc",
        },
        map: {
            pad: 10,
            borderWidth: 1,
            originX: NaN,
            originY: NaN,
            maxZoom: { usa: 4, world: 7 },
            zoomTransition: d3.transition().duration(500),
        },
        legend: {
            padLeft: 20,
            barWidth: 15,
            padRight: 20,
            height: { usa: 250, world: 230 },
            gradientID: "verticalLegendGradient",
        },
        title: {
            height: 40,
        },
        mapWidth: {},
        mapHeight: {},
    };
    pa.map.originX = pa.map.pad;
    pa.map.originY = pa.title.height + pa.map.pad;
    Object.keys(pa.width).forEach((key) => {
        const scope = key;
        pa.mapWidth[scope] =
            pa.width[scope] -
                pa.map.originX -
                (pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight) -
                pa.map.pad;
    });
    Object.keys(pa.height).forEach((key) => {
        const scope = key;
        pa.mapHeight[scope] = pa.height[scope] - pa.map.originY - pa.map.pad;
    });
    return pa;
})());
const dateFormatter = d3.timeFormat("%Y-%m-%d");
const tooltipDateFormatter = d3.timeFormat("%b %-d");
function getDateNDaysAfter(startDate, n) {
    return dateFormatter(new Date(dateStrParser(startDate).getTime() + n * MS_PER_DAY));
}
function moveTooltipTo(x, y) {
    tooltip.style("top", `${+y - 30}px`).style("left", `${+x + 10}px`);
}
function getFormatter(caseType, count, smoothAvgDays) {
    return (count === "dodd" && smoothAvgDays > 1) || isPerCapita(caseType)
        ? numberFormatters.float
        : numberFormatters.int;
}
function getDataOnDate({ feature, count, dateKey, caseType, smoothAvgDays, }) {
    if (typeof feature.covidData === "undefined") {
        return null;
    }
    const data = count === "dodd" ? feature.covidData.dodd : feature.covidData.net;
    const index = feature.covidData.date[dateKey];
    if (typeof index === "undefined") {
        return null;
    }
    smoothAvgDays = smoothAvgDays;
    let value;
    if (count === "dodd" && smoothAvgDays >= 2) {
        let sum = 0;
        for (let i = index; i > index - smoothAvgDays; --i) {
            const x = data[caseType][i];
            sum += x;
        }
        value = sum / smoothAvgDays;
        if (isNaN(value)) {
            return null;
        }
    }
    else {
        value = data[caseType][index];
    }
    return value;
}
function updateTooltip({ visibility }) {
    const { feature, count, dateKey, caseType, smoothAvgDays } = tooltip.datum();
    if (typeof feature === "undefined") {
        return;
    }
    const dateStr = tooltipDateFormatter(dateStrParser(dateKey).getTime() - MS_PER_DAY);
    const location = feature.properties.name;
    const value = getDataOnDate({
        feature,
        count,
        dateKey,
        caseType,
        smoothAvgDays,
    });
    const formatter = getFormatter(caseType, count, smoothAvgDays);
    const countStr = value === null ? "~No data~" : formatter(value);
    tooltip.html(`${dateStr}<br>${location}<br>${countStr}`);
    if (visibility !== "nochange") {
        tooltip.style("visibility", visibility);
    }
}
let mouseMoved = false;
let hasPlayedAnimation = false;
function updateMaps({ plotGroup, dateIndex, smoothAvgDays, }) {
    const { count, scopedCovidData, playbackInfo, } = plotGroup.datum();
    if (typeof dateIndex === "undefined" || dateIndex === null) {
        dateIndex = plotGroup.selectAll(".date-slider").node().value;
    }
    dateIndex = dateIndex;
    if (count === "dodd" &&
        (typeof smoothAvgDays === "undefined" || smoothAvgDays === null)) {
        smoothAvgDays = plotGroup.selectAll(".smooth-avg-slider").node().value;
    }
    else if (typeof smoothAvgDays === "undefined") {
        smoothAvgDays = 0;
    }
    else {
        smoothAvgDays = +smoothAvgDays;
    }
    smoothAvgDays = smoothAvgDays;
    const dateSliderNode = plotGroup
        .selectAll(".date-slider")
        .property("value", dateIndex)
        .node();
    plotGroup.selectAll(".smooth-avg-slider").property("value", smoothAvgDays);
    const minDate = scopedCovidData.agg.net.date.min_nonzero;
    const dateKey = getDateNDaysAfter(minDate, dateIndex);
    const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
    const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
    plotGroup.selectAll(".date-span").text(dateStr);
    plotGroup
        .selectAll(".smooth-avg-text")
        .text(`Moving avg: ${smoothAvgDays} day${smoothAvgDays > 1 ? "s" : ""}`);
    if (hasPlayedAnimation && !playbackInfo.isPlaying) {
        plotGroup
            .selectAll(".play-button")
            .text(dateIndex === +dateSliderNode.max ? "Restart" : "Play");
    }
    Object.assign(tooltip.datum(), { dateKey, smoothAvgDays });
    updateTooltip({ visibility: "nochange" });
    plotGroup
        .selectAll(".plot-container")
        .each(function ({ caseType }) {
        const plotContainer = d3.select(this);
        const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[count][caseType];
        const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);
        const svg = plotContainer.selectAll("svg").selectAll(".map");
        svg.selectAll("path")
            .attr("fill", (feature) => {
            const value = getDataOnDate({
                feature,
                count,
                dateKey,
                caseType,
                smoothAvgDays,
            });
            if (value === 0) {
                return plotAesthetics.colors.zero;
            }
            if (value === null || value < vmin) {
                return `url(#missingDataFillPattern)`;
            }
            return plotAesthetics.colors.scale(colorScale(value));
        })
            .classed("state-boundary", true)
            .on("mouseover", (d) => {
            tooltip.datum({
                ...tooltip.datum(),
                feature: d,
                caseType,
                count,
                smoothAvgDays,
            });
            updateTooltip({ visibility: "visible" });
        })
            .on("mousemove", () => {
            if (!mouseMoved) {
                const dateIndex = +dateSliderNode.value;
                tooltip.datum({
                    ...tooltip.datum(),
                    dateKey: getDateNDaysAfter(minDate, dateIndex),
                    smoothAvgDays,
                });
                updateTooltip({ visibility: "visible" });
            }
            mouseMoved = true;
            tooltip.style("visibility", "visible");
            moveTooltipTo(d3.event.pageX, d3.event.pageY);
        })
            .on("mouseout", () => {
            tooltip.style("visibility", "hidden");
            mouseMoved = false;
        });
    });
}
const numberFormatters = { int: d3.format(",~r"), float: d3.format(",.2f") };
const tooltip = d3
    .select("body")
    .selectAll()
    .data([{ dateKey: null, location: null, countStr: null }])
    .join("div")
    .attr("id", "map-tooltip");
let graphIsCurrentlyZooming = false;
function _initializeChoropleth({ plotGroup, allCovidData, allGeoData, }) {
    const { location, count, } = plotGroup.datum();
    const scopedCovidData = allCovidData[location];
    const scopedGeoData = allGeoData[location];
    const projectionExtent = [
        [0, 0],
        [
            plotAesthetics.mapWidth[location] - plotAesthetics.map.pad,
            plotAesthetics.mapHeight[location] - plotAesthetics.map.pad,
        ],
    ];
    const projection = (location === "usa"
        ? d3.geoAlbersUsa()
        : d3.geoTimes()).fitExtent(projectionExtent, scopedGeoData);
    const geoPath = d3.geoPath(projection);
    const zoom = d3
        .zoom()
        .scaleExtent([1, plotAesthetics.map.maxZoom[location]])
        .translateExtent([
        [0, 0],
        [plotAesthetics.width[location], plotAesthetics.height[location]],
    ])
        .filter(function () {
        return (d3.event.type !== "dblclick" &&
            (d3.event.type !== "wheel" || d3.event.shiftKey) &&
            (!d3.event.touches || d3.event.touches.length === 2));
    })
        .on("zoom", function () {
        tooltip.style("visibility", "hidden");
        const transform = d3.event.transform;
        d3.select(this).selectAll(".map").attr("transform", transform);
        const mapContainer = this;
        if (!graphIsCurrentlyZooming) {
            graphIsCurrentlyZooming = true;
            plotGroup.selectAll(".map-container").each(function () {
                if (this !== mapContainer) {
                    zoom.transform(d3.select(this), transform);
                }
            });
            graphIsCurrentlyZooming = false;
        }
        plotGroup
            .selectAll(".state-boundary")
            .attr("stroke-width", plotAesthetics.map.borderWidth / transform.k);
    });
    Object.assign(plotGroup.datum(), { scopedCovidData });
    const legendTransX = plotAesthetics.mapWidth[location] + plotAesthetics.legend.padLeft;
    const legendTransY = (plotAesthetics.title.height +
        plotAesthetics.height[location] -
        plotAesthetics.legend.height[location]) /
        2;
    const { min_nonzero: minDate, max: maxDate } = scopedCovidData.agg.net.date;
    const firstDay = dateStrParser(minDate);
    const lastDay = dateStrParser(maxDate);
    const daysElapsed = Math.round((lastDay - firstDay) / MS_PER_DAY);
    plotGroup.selectAll(".plot-container").each(function () {
        const plotContainer = d3.select(this);
        const caseType = plotContainer.datum().caseType;
        const svg = plotContainer.selectAll("svg");
        const mainPlotArea = svg.selectAll("g.main-plot-area");
        const mapContainer = mainPlotArea
            .selectAll()
            .data([
            {
                tx: plotAesthetics.map.originX,
                ty: plotAesthetics.map.originY,
            },
        ])
            .join("g")
            .classed("map-container", true)
            .attr("transform", (d) => `translate(${d.tx},${d.ty})`);
        mapContainer
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", plotAesthetics.mapWidth[location])
            .attr("height", plotAesthetics.mapHeight[location])
            .attr("fill-opacity", 0)
            .attr("stroke", "#ccc")
            .attr("stroke-width", 1);
        mapContainer.on("dblclick", function () {
            const mc = d3.select(this);
            const t = plotAesthetics.map.zoomTransition;
            mc.transition(t).call(zoom.transform, d3.zoomIdentity);
            mc.selectAll(".state-boundary")
                .transition(t)
                .attr("stroke-width", plotAesthetics.map.borderWidth);
        });
        mapContainer
            .append("g")
            .classed("map", true)
            .selectAll("path")
            .data(scopedGeoData.features)
            .join("path")
            .attr("d", geoPath)
            .attr("stroke", "#fff8")
            .attr("stroke-width", plotAesthetics.map.borderWidth);
        mapContainer.call(zoom);
        const legend = svg
            .append("g")
            .attr("transform", `translate(${legendTransX} ${legendTransY})`);
        const { barWidth, height: barHeights } = plotAesthetics.legend;
        const barHeight = barHeights[location];
        legend
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", barWidth)
            .attr("height", barHeight)
            .attr("fill", `url(#${plotAesthetics.legend.gradientID})`);
        const { min_nonzero: vmin, max: vmax } = scopedCovidData.agg[count][caseType];
        const legendScale = d3
            .scaleLog()
            .nice()
            .base(10)
            .domain([vmin, vmax])
            .range([barHeight, 0]);
        const nLegendTicks = 7;
        legendScale.ticks(nLegendTicks).forEach((y) => {
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
        const bigNumberTickFormatter = legendScale.tickFormat(nLegendTicks, isPerCapita(caseType) ? "~g" : "~s");
        const smallNumberTickFormatter = legendScale.tickFormat(nLegendTicks, count === "net" ? "~g" : "~r");
        legendScale.ticks(nLegendTicks).forEach((y) => {
            const formatter = y < 1 ? smallNumberTickFormatter : bigNumberTickFormatter;
            legend
                .append("text")
                .attr("x", barWidth + 4)
                .attr("y", legendScale(y))
                .text(`${formatter(y)}`)
                .attr("fill", "black")
                .attr("font-size", 12)
                .attr("text-anchor", "left")
                .attr("alignment-baseline", "middle");
        });
        const titlePrefixStr = count === "dodd" ? "New Daily" : "Total";
        let caseTypeStr = caseType;
        let titleSuffixStr = "";
        if (isPerCapita(caseType)) {
            caseTypeStr = caseTypeStr.replace("_per_capita", "");
            titleSuffixStr = " Per 100,000 People";
        }
        caseTypeStr = caseTypeStr.replace(/^./, (c) => c.toUpperCase());
        const titleStr = `${titlePrefixStr} ${caseTypeStr}${titleSuffixStr}`;
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
        });
    });
    updateMaps({
        plotGroup,
        dateIndex: daysElapsed,
        smoothAvgDays: null,
    });
}
let PlaybackInfo = (() => {
    class PlaybackInfo {
        constructor() {
            this.isPlaying = false;
            this.selectedIndex = PlaybackInfo.speeds.indexOf(PlaybackInfo.defaultSpeed);
            this.timerElapsedTimeProptn = 0;
        }
        get baseIntervalMS() {
            return 1000;
        }
        get currentIntervalMS() {
            return this.baseIntervalMS / PlaybackInfo.speeds[this.selectedIndex];
        }
    }
    PlaybackInfo.speeds = [0.25, 0.5, 1, 2, 4];
    PlaybackInfo.defaultSpeed = 1;
    return PlaybackInfo;
})();
const plotGroups = d3
    .select("#map-plots")
    .selectAll()
    .data(SCOPES.map(scope => ({ ...scope, playbackInfo: new PlaybackInfo() })))
    .join("div")
    .classed("plot-scope-group", true);
const plotContainers = plotGroups
    .selectAll()
    .data(function (scope) {
    return [
        "cases",
        "cases_per_capita",
        "deaths",
        "deaths_per_capita",
    ].map((caseType) => ({
        ...scope,
        caseType,
        plotGroup: d3.select(this),
    }));
})
    .join("div")
    .classed("plot-container", true);
const svgs = plotContainers
    .append("svg")
    .classed("plot", true)
    .attr("width", (d) => plotAesthetics.width[d.location])
    .attr("height", (d) => plotAesthetics.height[d.location]);
(() => {
    plotGroups.each(function ({ count, playbackInfo, }) {
        const plotGroup = d3.select(this);
        const plotContainers = plotGroup.selectAll(".plot-container");
        const dateSliderRows = plotContainers
            .append("div")
            .classed("input-row", true)
            .append("span");
        dateSliderRows
            .append("span")
            .classed("date-span", true)
            .classed("slider-text", true);
        dateSliderRows
            .selectAll()
            .data(() => [{ plotGroup }])
            .join("input")
            .classed("date-slider", true)
            .classed("input-slider", true)
            .attr("type", "range")
            .attr("min", 0)
            .attr("max", 1)
            .property("value", 1)
            .on("input", function (d) {
            const dateIndex = +this.value;
            updateMaps({
                plotGroup: d.plotGroup,
                dateIndex,
            });
        });
        if (count === "dodd") {
            const smoothAvgSliderRows = plotContainers
                .append("div")
                .classed("input-row", true)
                .append("span");
            smoothAvgSliderRows
                .append("span")
                .classed("smooth-avg-text", true)
                .classed("slider-text", true);
            smoothAvgSliderRows
                .selectAll()
                .data(() => [{ plotGroup }])
                .join("input")
                .classed("smooth-avg-slider", true)
                .classed("input-slider", true)
                .attr("type", "range")
                .attr("min", 1)
                .attr("max", 7)
                .property("value", 1)
                .on("input", function (d) {
                const smoothAvgDays = +this.value;
                updateMaps({
                    plotGroup: d.plotGroup,
                    smoothAvgDays,
                });
            });
        }
        const buttonsRows = plotGroup
            .selectAll(".plot-container")
            .append("div")
            .classed("button-row", true)
            .append("span")
            .classed("button-container", true);
        const buttonSpans = buttonsRows
            .append("span")
            .classed("speed-buttons-span", true);
        const playButtons = buttonSpans
            .selectAll()
            .data(() => [playbackInfo])
            .join("button")
            .classed("play-button", true)
            .text("Play");
        const dateSliders = plotGroup.selectAll(".date-slider");
        const dateSliderNode = dateSliders.node();
        function haltPlayback(playbackInfo) {
            playbackInfo.isPlaying = false;
            clearInterval(playbackInfo.timer);
            const now = new Date();
            const elapsedTimeMS = now.getTime() - playbackInfo.timerStartDate.getTime();
            playbackInfo.timerElapsedTimeProptn +=
                elapsedTimeMS / playbackInfo.currentIntervalMS;
        }
        function startPlayback(playbackInfo) {
            playbackInfo.isPlaying = true;
            const maxDateIndex = parseFloat(dateSliderNode.max);
            if (dateSliderNode.value === dateSliderNode.max) {
                updateMaps({ plotGroup, dateIndex: 0 });
                playbackInfo.timerElapsedTimeProptn = 0.0000001;
            }
            function updateDate() {
                playbackInfo.timerStartDate = new Date();
                playbackInfo.timerElapsedTimeProptn = 0;
                const dateIndex = parseFloat(dateSliderNode.value);
                if (dateIndex < maxDateIndex) {
                    updateMaps({
                        plotGroup,
                        dateIndex: dateIndex + 1,
                    });
                }
                if (dateIndex >= maxDateIndex - 1) {
                    clearInterval(playbackInfo.timer);
                    playbackInfo.isPlaying = false;
                    playButtons.text("Restart");
                }
            }
            playbackInfo.timerStartDate = new Date();
            const timeRemainingProptn = 1 - playbackInfo.timerElapsedTimeProptn;
            const initialIntervalMS = timeRemainingProptn === 1
                ? 0
                : timeRemainingProptn * playbackInfo.currentIntervalMS;
            playbackInfo.timer = setTimeout(() => {
                updateDate();
                playbackInfo.timer = setInterval(updateDate, playbackInfo.currentIntervalMS);
            }, initialIntervalMS);
        }
        playButtons.on("click", function (playbackInfo) {
            if (playbackInfo.isPlaying) {
                haltPlayback(playbackInfo);
                playButtons.text("Play");
            }
            else {
                hasPlayedAnimation = true;
                startPlayback(playbackInfo);
                playButtons.text("Pause");
            }
        });
        const speedButtons = buttonSpans
            .selectAll()
            .data(() => PlaybackInfo.speeds.map(speed => {
            return { speed, playbackInfo };
        }))
            .join("button")
            .classed("speed-button", true)
            .text(({ speed }) => `${speed}x`)
            .property("disabled", ({ speed }) => speed === PlaybackInfo.defaultSpeed);
        speedButtons.on("click", function ({ speed, playbackInfo, }, i) {
            const wasPlaying = playbackInfo.isPlaying;
            if (wasPlaying) {
                haltPlayback(playbackInfo);
            }
            playbackInfo.selectedIndex = i;
            speedButtons.each(function (d) {
                d3.select(this).property("disabled", d.speed === speed);
            });
            if (wasPlaying) {
                startPlayback(playbackInfo);
            }
        });
    });
})();
(() => {
    plotGroups.each(function (scope) {
        const svgs = d3.select(this).selectAll("svg");
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
        const canvases = svgs.append("g").classed("main-plot-area", true);
        const clipPathID = `plot-clip-${scope.location}-${scope.count}`;
        defs.append("clipPath")
            .attr("id", clipPathID)
            .append("rect")
            .attr("x", plotAesthetics.map.originX)
            .attr("y", plotAesthetics.map.originY)
            .attr("width", plotAesthetics.mapWidth[scope.location])
            .attr("height", plotAesthetics.mapHeight[scope.location]);
        defs.append("pattern")
            .attr("id", "missingDataFillPattern")
            .attr("patternUnits", "userSpaceOnUse")
            .attr("width", 8)
            .attr("height", 8)
            .append("path")
            .attr("d", "M-2,2 l3,-3 M0,8 l8,-8 M6,10 l3,-3")
            .style("stroke", plotAesthetics.colors.missing)
            .style("stroke-width", 2);
        canvases.attr("clip-path", `url(#${clipPathID})`);
    });
})();
export function initializeChoropleths(allCovidData, allGeoData) {
    plotGroups.each(function () {
        const plotGroup = d3.select(this);
        _initializeChoropleth({
            plotGroup,
            allCovidData,
            allGeoData,
        });
    });
}
