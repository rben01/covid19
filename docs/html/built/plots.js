const MS_PER_DAY = 86400 * 1000;
const plotAesthetics = Object.freeze((() => {
    const pa = {
        width: { usa: 500, world: 600 },
        height: { usa: 350, world: 400 },
        colors: {
            scale: (t) => d3.interpolateCividis(1 - t),
            nSteps: 101,
            missing: "#ccc",
            zero: "#ddc",
        },
        map: {
            pad: 10,
            borderWidth: 1,
            originX: null,
            originY: null,
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
        mapWidth: null,
        mapHeight: null,
    };
    pa.map.originX = pa.map.pad;
    pa.map.originY = pa.title.height + pa.map.pad;
    pa.mapWidth = {};
    Object.keys(pa.width).forEach((scope) => {
        pa.mapWidth[scope] =
            pa.width[scope] -
                pa.map.originX -
                (pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight);
    });
    pa.mapHeight = {};
    Object.keys(pa.height).forEach((scope) => {
        pa.mapHeight[scope] = pa.height[scope] - pa.map.originY - pa.map.pad;
    });
    return pa;
})());
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
const mouseActions = {
    mouseover: null,
    mousemove: null,
    mouseout: null,
};
function updateMaps({ plotGroup, dateIndex }) {
    plotGroup.selectAll(".date-slider").property("value", dateIndex);
    const minDate = plotGroup.datum().scopedCovidData.agg.date.min_nonzero;
    const dateKey = getDateNDaysAfter(minDate, dateIndex);
    const trueDate = getDateNDaysAfter(minDate, dateIndex - 1);
    const dateStr = d3.timeFormat("%b %e, %Y")(dateStrParser(trueDate));
    plotGroup.selectAll(".date-span").text(dateStr);
    plotGroup
        .selectAll(".plot-container")
        .each(function ({ caseType, plotGroup, }) {
        const plotContainer = d3.select(this);
        const formatter = isPerCapita(caseType)
            ? numberFormatters.float
            : numberFormatters.int;
        const { min_nonzero: vmin, max: vmax, } = plotGroup.datum().scopedCovidData.agg[caseType];
        const colorScale = d3.scaleLog().domain([vmin, vmax]).range([0, 1]);
        const svg = plotContainer.selectAll("svg").selectAll("g");
        mouseActions.mouseover = (d) => {
            const noDataStr = "~No data~";
            const caseCount = (() => {
                if (typeof d.covidData === "undefined") {
                    return noDataStr;
                }
                const index = d.covidData.date[dateKey];
                if (typeof index === "undefined") {
                    return noDataStr;
                }
                return formatter(d.covidData[caseType][index]);
            })();
            tooltip.html(`${dateKey}<br>${d.properties.name}<br>${caseCount}`);
            return tooltip.style("visibility", "visible");
        };
        mouseActions.mousemove = () => tooltip
            .style("top", `${+d3.event.pageY - 30}px`)
            .style("left", `${+d3.event.pageX + 10}px`);
        mouseActions.mouseout = () => tooltip.style("visibility", "hidden");
        svg.selectAll("path")
            .attr("fill", (d) => {
            if (typeof d.covidData === "undefined") {
                return plotAesthetics.colors.missing;
            }
            const index = d.covidData.date[dateKey];
            if (typeof index === "undefined") {
                return plotAesthetics.colors.missing;
            }
            const value = d.covidData[caseType][index];
            if (value < vmin) {
                return plotAesthetics.colors.zero;
            }
            return plotAesthetics.colors.scale(colorScale(value));
        })
            .classed("state-boundary", true)
            .on("mouseover", mouseActions.mouseover)
            .on("mousemove", mouseActions.mousemove)
            .on("mouseout", mouseActions.mouseout);
    });
}
const numberFormatters = { int: d3.format(",~r"), float: d3.format(",.2f") };
const tooltip = d3.select("body").append("div").attr("id", "tooltip");
function getDragBox({ dragX, dragY, originX, originY, aspectRatio, scope, }) {
    let x = dragX;
    let y = dragY;
    let width = Math.abs(x - originX);
    let height = Math.abs(y - originY);
    const givenAspectRatio = width / height;
    if (givenAspectRatio > aspectRatio) {
        height = width / aspectRatio;
        if (y < originY) {
            y = originY - height;
        }
    }
    else if (givenAspectRatio < aspectRatio) {
        width = height * aspectRatio;
        if (x < originX) {
            x = originX - width;
        }
    }
    return {
        x: Math.min(x, originX),
        y: Math.min(y, originY),
        width,
        height,
        scaleFactor: plotAesthetics.mapWidth[scope] / width,
    };
}
function initializeChoropleth({ plotGroup, allCovidData, allGeoData, }) {
    const scope = plotGroup.datum().scope;
    const scopedCovidData = allCovidData[scope];
    const scopedGeoData = allGeoData[scope];
    plotGroup.datum({ ...plotGroup.datum(), scopedCovidData });
    const projection = (scope === "usa"
        ? d3.geoAlbersUsa()
        : d3.geoNaturalEarth1()).fitExtent([
        [0, plotAesthetics.title.height + plotAesthetics.map.pad],
        [plotAesthetics.mapWidth[scope], plotAesthetics.height[scope]],
    ], scopedGeoData);
    const zoom = d3
        .zoom()
        .scaleExtent([1, 10])
        .translateExtent([
        [0, 0],
        [plotAesthetics.width[scope], plotAesthetics.height[scope]],
    ]);
    const dragState = { distSq: 0 };
    const aspectRatio = plotAesthetics.mapWidth[scope] / plotAesthetics.mapHeight[scope];
    const drag = d3
        .drag()
        .on("start", function () {
        dragState.distSq = 0;
        const { x, y } = d3.event;
        const canvas = d3.select(this);
        canvas
            .selectAll()
            .data([{ originX: x, originY: y }])
            .join("rect")
            .attr("id", "drag-box")
            .attr("stroke", "#ccc")
            .attr("stroke-width", 3)
            .attr("fill", "#0002")
            .attr("x", x)
            .attr("y", y);
        tooltip.style("visibility", "hidden");
        const states = canvas.selectAll(".state-boundary");
        Object.keys(mouseActions).forEach(action => {
            states.on(action, null);
        });
    })
        .on("drag", function () {
        dragState.distSq += d3.event.dx * d3.event.dx + d3.event.dy * d3.event.dy;
        const rect = d3.select(this).selectAll("#drag-box");
        const { originX, originY } = rect.datum();
        let { x: dragX, y: dragY } = d3.event;
        const { x, y, width, height } = getDragBox({
            dragX,
            dragY,
            originX,
            originY,
            aspectRatio,
            scope,
        });
        rect.attr("x", x).attr("width", width).attr("y", y).attr("height", height);
    })
        .on("end", function () {
        const canvases = plotGroup.selectAll(".main-plot-area");
        const rect = canvases.selectAll("#drag-box");
        const { originX, originY } = rect.datum();
        let { x: dragX, y: dragY } = d3.event;
        rect.remove();
        const map = canvases.selectAll(".map-container");
        const states = map.selectAll(".state-boundary");
        Object.entries(mouseActions).forEach(([action, f]) => {
            states.on(action, f);
        });
        // If we didn't drag far, don't do any transformation
        if (dragState.distSq < 10) {
            return;
        }
        // Calculate transform
        const { x: x1, y: y1, width, height, scaleFactor } = getDragBox({
            dragX,
            dragY,
            originX,
            originY,
            aspectRatio,
            scope,
        });
        const x2 = x1 + width;
        const y2 = y1 + height;
        const currentTransform = map.attr("transform") || "matrix(1 0 0 1 0 0)";
        const reMatch = currentTransform.match(/-?\d+\.?\d*/g);
        const prevScaleX = +reMatch[0];
        const prevScaleY = +reMatch[3];
        const prevTranslateX = +reMatch[4];
        const prevTranslateY = +reMatch[5];
        console.log(prevScaleX, prevScaleY, prevTranslateX, prevTranslateY);
        const prevScaledWidth = plotAesthetics.width[scope] * prevScaleX;
        const prevScaledHeight = plotAesthetics.height[scope] * prevScaleY;
        const scaleX = prevScaledWidth / (x2 - x1);
        const scaleY = prevScaledHeight / (y2 - y1);
        const translateX = prevTranslateX * prevScaleY - x1 * (prevScaledWidth / (x2 - x1));
        const translateY = prevTranslateY * prevScaleX - y1 * (prevScaledHeight / (y2 - y1));
        map.attr("transform", `matrix(${scaleX} 0 0 ${scaleY} ${translateX} ${translateY})`);
        console.log(map.attr("transform"));
        states.attr("stroke-width", plotAesthetics.map.borderWidth / scaleFactor);
    });
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
        const mainPlotArea = svg.selectAll("g.main-plot-area");
        mainPlotArea.call(drag);
        const canvas = mainPlotArea.append("g").classed("map-container", true);
        const path = d3.geoPath(projection);
        canvas
            .selectAll("path")
            .data(scopedGeoData.features)
            .join("path")
            .attr("d", path)
            .attr("stroke", "#fff8")
            .attr("stroke-width", plotAesthetics.map.borderWidth);
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
    updateMaps({ plotGroup, dateIndex: daysElapsed });
}
const plotGroups = d3
    .select("#content")
    .selectAll()
    .data([{ scope: "usa" }])
    .join("div")
    .classed("plot-scope-group", true);
const plotDivs = plotGroups
    .selectAll()
    .data(function ({ scope }) {
    return ["cases", "cases_per_capita", "deaths", "deaths_per_capita"].map((caseType) => ({
        scope,
        caseType,
        plotGroup: d3.select(this),
    }));
})
    .join("div")
    .classed("plot-container", true);
const svgs = plotDivs
    .append("svg")
    .classed("plot", true)
    .attr("width", (d) => plotAesthetics.width[d.scope])
    .attr("height", (d) => plotAesthetics.height[d.scope]);
const sliderRows = plotDivs.append("div").append("span");
const dateSpans = sliderRows.append("span").classed("date-span", true);
const sliders = sliderRows
    .selectAll()
    .data(function ({ scope }) {
    return [{ plotGroup: plotGroups.filter((p) => p.scope === scope) }];
})
    .enter()
    .append("input")
    .classed("date-slider", true)
    .attr("type", "range")
    // Temporary values, used to place the slider's knob to the right while we await the actual data we'll use to compute its range
    .attr("min", 0)
    .attr("max", 1)
    .property("value", 1)
    .on("input", function (d) {
    const dateIndex = +this.value;
    updateMaps({ plotGroup: d.plotGroup, dateIndex });
});
const buttonsRow = plotDivs.append("div").append("span");
buttonsRow.append("button").classed("play-button", true);
// Create defs: gradient and clipPath
(() => {
    plotGroups.each(function ({ scope }) {
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
        const clipPathID = `plot-clip-${scope}`;
        defs.append("clipPath")
            .attr("id", clipPathID)
            .append("rect")
            .attr("x", plotAesthetics.map.originX)
            .attr("y", plotAesthetics.map.originY)
            .attr("width", plotAesthetics.mapWidth[scope])
            .attr("height", plotAesthetics.mapHeight[scope]);
        canvases.attr("clip-path", `url(#${clipPathID})`);
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
