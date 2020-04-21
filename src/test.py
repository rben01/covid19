# %%
import pandas as pd
from bokeh.io import show, output_notebook
from bokeh.models import LogColorMapper
from bokeh.palettes import Viridis6 as palette
from bokeh.plotting import figure
from bokeh.sampledata.unemployment import data as unemployment
from bokeh.sampledata.us_counties import data as counties

output_notebook()
palette = tuple(reversed(palette))


counties = {
    code: county
    for code, county in counties.items()
    if county["state"] == "ca" and county["name"] == "Santa Barbara"
}

# for i, (k, v) in enumerate(counties.items()):
#     if v["name"] == "Santa Barbara":
#         print(v)
#         print(k)
#         break


county_xs_o = [county["lons"] for county in counties.values()]
county_ys_o = [county["lats"] for county in counties.values()]

county_xs = county_xs_o
county_ys = county_ys_o

for s in [county_xs, county_ys]:
    for L in s:
        for i, x in enumerate(L):
            if pd.isna(x):
                L[i] = 'NaN'


print(county_xs)


county_names = [county["name"] for county in counties.values()]
county_rates = [unemployment[county_id] for county_id in counties]
color_mapper = LogColorMapper(palette=palette)

data = dict(x=county_xs, y=county_ys, name=county_names, rate=county_rates)


TOOLS = "pan,wheel_zoom,reset,hover,save"

p = figure(
    title="Texas Unemployment, 2009",
    tools=TOOLS,
    x_axis_location=None,
    y_axis_location=None,
    tooltips=[
        ("Name", "@name"),
        ("Unemployment rate", "@rate%"),
        ("(Long, Lat)", "($x, $y)"),
    ],
)
p.grid.grid_line_color = None
p.hover.point_policy = "follow_mouse"

p.patches(
    "x",
    "y",
    source=data,
    fill_color={"field": "rate", "transform": color_mapper},
    fill_alpha=0.7,
    line_color="white",
    line_width=0.5,
)

show(p)
