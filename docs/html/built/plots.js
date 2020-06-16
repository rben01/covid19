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
            pad: 25,
            borderWidth: 1,
            originX: NaN,
            originY: NaN,
            zoomTransition: d3.transition().duration(500),
        },
        legend: {
            padLeft: 20,
            barWidth: 15,
            padRight: 40,
            height: 275,
            gradientID: "verticalLegendGradient",
        },
        title: {
            height: 100,
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
                (pa.legend.padLeft + pa.legend.barWidth + pa.legend.padRight) -
                pa.map.pad;
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
    info: { prevFeature: null },
};
function moveTooltipAbsolute(x, y) {
    tooltip.style("top", `${+y - 30}px`).style("left", `${+x + 10}px`);
}
function moveTooltipRelative(dx, dy) {
    const top = parseFloat(tooltip.style("top"));
    const left = parseFloat(tooltip.style("left"));
    console.log(top, left, tooltip.style("top"), tooltip.style("left"));
    tooltip.style("top", `${top + dy}px`).style("top", `${left + dx}px`);
}
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
            if (d === mouseActions.info.prevFeature) {
                return;
            }
            mouseActions.info.prevFeature = d;
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
        mouseActions.mousemove = () => {
            tooltip.style("visibility", "visible");
            moveTooltipAbsolute(d3.event.pageX, d3.event.pageY);
        };
        mouseActions.mouseout = () => {
            tooltip.style("visibility", "hidden");
            mouseActions.info.prevFeature = null;
        };
        const p = svg
            .selectAll("path")
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
            .classed("state-boundary", true);
        Object.entries(mouseActions).forEach(([event, action]) => [
            p.on(event, action),
        ]);
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
// https://bl.ocks.org/mthh/8f97dda227d21163773b0a714a573856
function dispatchMouseToMap(event, type) {
    const { pageX, pageY, clientX, clientY } = event;
    const elems = document.elementsFromPoint(pageX, pageY);
    const elem = elems.find(e => d3.select(e).classed("state-boundary"));
    if (elem) {
        d3.select(elem).each((d) => mouseActions.mouseover(d));
        const new_click_event = new MouseEvent(type, {
            pageX: pageX,
            pageY: pageY,
            clientX: clientX,
            clientY: clientY,
            bubbles: true,
            cancelable: true,
            view: window,
        });
        elem.dispatchEvent(new_click_event);
    }
    else {
        mouseActions.mouseout();
        // clearTimeout(t);
        // t = setTimeout(() => {
        // 	svg.select(".tooltip").style("display", "none");
        // }, 5);
    }
}
function initializeChoropleth({ plotGroup, allCovidData, allGeoData, }) {
    const scope = plotGroup.datum().scope;
    const scopedCovidData = allCovidData[scope];
    const scopedGeoData = allGeoData[scope];
    const projectionExtent = [
        [0, 0],
        [plotAesthetics.mapWidth[scope], plotAesthetics.mapHeight[scope]],
    ];
    const projection = (scope === "usa" ? d3.geoAlbersUsa() : d3.geoNaturalEarth1())
        .fitExtent(projectionExtent, scopedGeoData)
        .precision(0.001);
    const initialPrecision = projection.precision();
    const path = d3.geoPath(projection);
    const brushState = {
        distSq: 0,
        originX: NaN,
        originY: NaN,
        mousePos: 0,
        brushIsMoving: false,
        extent: {
            x1: 0,
            y1: 0,
            x2: plotAesthetics.mapWidth[scope],
            y2: plotAesthetics.mapHeight[scope],
        },
    };
    const zoom = d3
        .zoom()
        .scaleExtent([1, 10])
        .translateExtent([
        [0, 0],
        [plotAesthetics.width[scope], plotAesthetics.height[scope]],
    ])
        // .filter(function () {
        // 	return d3.event.type === "wheel";
        // })
        .on("start", function () {
        brushState.mousePos = d3.mouse(this);
        tooltip.style("visibility", "hidden");
    })
        .on("zoom", function () {
        const transform = d3.event.transform;
        // moveTooltipRelative(transform.x, transform.y);
        d3.select(this).selectAll(".map").attr("transform", transform);
        plotGroup
            .selectAll(".state-boundary")
            .attr("stroke-width", plotAesthetics.map.borderWidth / transform.k);
    })
        .on("end", function () {
        // tooltip.style("visibility", "visible");
    });
    // .filter(function () {
    // 	console.log(d3.event.type);
    // 	return (
    // 		d3.event.type === "mousedown" ||
    // 		(d3.event.ctrlKey && d3.event.type === "wheel")
    // 	);
    // });
    // https://bl.ocks.org/mbostock/f48fcdb929a620ed97877e4678ab15e6
    let idleTimeout = null;
    const idleDelay = 350;
    const idled = () => {
        idleTimeout = null;
    };
    const brush = d3
        .brush()
        .extent([
        [0, 0],
        [plotAesthetics.mapWidth[scope], plotAesthetics.mapHeight[scope]],
    ])
        .on("start", function () {
        if (brushState.brushIsMoving) {
            return;
        }
        console.log("brushstart");
        mouseActions.mouseout();
        const [[x1, y1]] = d3.event.selection;
        brushState.originX = x1;
        brushState.originY = y1;
    })
        .on("brush", function () {
        if (brushState.brushIsMoving) {
            return;
        }
        console.log("brushbrush");
        const [mouseX, mouseY] = d3.mouse(this);
        const { originX, originY } = brushState;
        brushState.distSq += d3.event.dx * d3.event.dx + d3.event.dy * d3.event.dy;
        let [[x1, y1], [x2, y2]] = d3.event.selection;
        let width = x2 - x1;
        let height = y2 - y1;
        const brushedAspectRatio = width / height;
        if (brushedAspectRatio > aspectRatio) {
            height = width / aspectRatio;
            if (mouseY < originY) {
                y1 = y2 - height;
            }
            else {
                y2 = y1 + height;
            }
        }
        else if (brushedAspectRatio < aspectRatio) {
            width = height * aspectRatio;
            if (mouseX < originX) {
                x1 = x2 - width;
            }
            else {
                x2 = x1 + width;
            }
        }
        brushState.brushIsMoving = true;
        brush.move(d3.select(this), [
            [x1, y1],
            [x2, y2],
        ]);
        brushState.brushIsMoving = false;
    })
        .on("end", function () {
        if (brushState.brushIsMoving) {
            return;
        }
        const s = d3.event.selection;
        brushState.distSq = 0;
        if (!s) {
            console.log(s, idleTimeout);
            if (!idleTimeout) {
                idleTimeout = setTimeout(idled, idleDelay);
                return;
            }
            projection.fitExtent(projectionExtent, scopedGeoData);
            plotGroup
                .selectAll(".state-boundary")
                .transition(plotAesthetics.map.zoomTransition)
                .attr("d", path);
        }
        else {
            // const {
            // 	x1: extentX1i,
            // 	y1: extentY1i,
            // 	x2: extentX2i,
            // 	y2: extentY2i,
            // } = brushState.extent;
            // const [[extentLon1i, extentLat1i], [extentLon2i, extentLat2i]] = [
            // 	[extentX1i, extentY1i],
            // 	[extentX2i, extentY2i],
            // ].map(projection.invert);
            const [[extentLon1f, extentLat1f], [extentLon2f, extentLat2f]] = s.map(projection.invert);
            const lon1 = extentLon1f;
            const lat1 = extentLat1f;
            const lon2 = extentLon2f;
            const lat2 = extentLat2f;
            const dummyGeoJSON = {
                type: "Polygon",
                coordinates: [
                    [
                        [lon1, lat1],
                        [lon2, lat1],
                        [lon2, lat2],
                        [lon1, lat2],
                    ],
                ],
            };
            // projection.precision(0.05);
            const states = plotGroup.selectAll(".state-boundary");
            // states.attr("d", path);
            projection.fitExtent(projectionExtent, dummyGeoJSON);
            states.attr("d", path);
            // const t = plotGroup
            // 	.selectAll(".state-boundary")
            // 	.transition()
            // 	.duration(1000);
            // console.log(t);
            // t.attr("d", path);
            // console.log("done");
            // const t = plotGroup
            // 	.selectAll(".state-boundary")
            // 	.transition(plotAesthetics.map.zoomTransition)
            // 	.attr("d", path)
            // 	.transition(plotAesthetics.map.zoomTransition)
            // 	.attr("d", path);
            // projection.precision(initialPrecision);
            // t.transition(plotAesthetics.map.zoomTransition).attr("d", path);
        }
        brushState.brushIsMoving = true;
        brush.clear(d3.select(this));
        brushState.brushIsMoving = false;
    });
    plotGroup.datum({ ...plotGroup.datum(), scopedCovidData });
    const aspectRatio = plotAesthetics.mapWidth[scope] / plotAesthetics.mapHeight[scope];
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
        mainPlotArea
            .append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", 100)
            .attr("height", 100)
            .attr("fill", "green");
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
            .attr("transform", (d) => `translate(${d.tx},${d.ty})`)
            .attr("width", (d) => plotAesthetics.mapWidth[scope] - d.tx)
            .attr("height", (d) => plotAesthetics.mapHeight[scope] - d.ty);
        const map = mapContainer
            .append("g")
            .classed("map", true)
            .attr("transform", "translate(0 0)"); // A dummy transform just so it exists
        map.selectAll("path")
            .data(scopedGeoData.features)
            .join("path")
            .attr("d", path)
            .attr("stroke", "#fff8")
            .attr("stroke-width", plotAesthetics.map.borderWidth)
            .attr("pointer-events", "all");
        // mapContainer.append("g").classed("brush", true).call(brush);
        mapContainer.call(zoom);
        // mapContainer.select(".brush").on("mousemove mousedown", function () {
        // 	dispatchMouseToMap(d3.event, "mousemove");
        // });
        const legend = svg
            .append("g")
            .attr("transform", `translate(${legendTransX} ${legendTransY})`);
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
