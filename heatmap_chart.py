"""热力图 figure 构建（与 Streamlit 解耦，方便单独测试）。"""

import math

import numpy as np
import plotly.graph_objects as go

WEEK_CN = "一二三四五六日"
# 【修改点】将原来的深灰色改为极浅的灰白，达到若隐若现的效果
GRID_COLOR = "#EBEBEB" 


def build_heatmap_figure(
    matrix,
    days,
    color_map,
    subjects_order,
    n_slots=48,
    grid_color=GRID_COLOR,
):
    """自然日 00:00-24:00 热力图；细暗色网格线，空格为白色。"""
    slot_minutes = 24 * 60 // n_slots
    slot_label = [
        f"{(i * slot_minutes) // 60:02d}:{(i * slot_minutes) % 60:02d}" for i in range(n_slots)
    ]
    slot_range = [
        f"{slot_label[i]}-{slot_label[i + 1] if i + 1 < n_slots else '24:00'}"
        for i in range(n_slots)
    ]

    present = {v for v in matrix.to_numpy().ravel() if isinstance(v, str) and v}
    subjects = [s for s in subjects_order if s in present]
    subjects += [s for s in sorted(present) if s not in subjects]

    index = {s: i for i, s in enumerate(subjects)}
    n_colors = len(subjects) + 1          # 最后一种颜色给“无记录”
    missing = len(subjects)

    z = np.full(matrix.shape, missing, dtype=float)
    custom = np.empty(matrix.shape, dtype=object)

    for j, day in enumerate(days):
        day_str = f"{day:%m-%d} 周{WEEK_CN[day.weekday()]}"
        for i in range(n_slots):
            value = matrix.iat[i, j]
            if isinstance(value, str) and value:
                z[i, j] = index.get(value, missing)
                custom[i, j] = f"{day_str}<br>{slot_range[i]}<br><b>{value}</b>"
            else:
                custom[i, j] = f"{day_str}<br>{slot_range[i]}<br>无记录"

    colorscale = []
    for i, s in enumerate(subjects):
        color = color_map.get(s, '#999999')
        colorscale.append([i / n_colors, color])
        colorscale.append([(i + 1) / n_colors, color])
    colorscale.append([len(subjects) / n_colors, "#FFFFFF"])
    colorscale.append([1.0, "#FFFFFF"])

    step = max(1, math.ceil(len(days) / 24))
    tickvals = list(range(0, len(days), step))
    ticktext = [f"{days[i]:%m-%d}" for i in tickvals]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(range(len(days))),
            y=list(range(n_slots)),
            colorscale=colorscale,
            zmin=-0.5,
            zmax=n_colors - 0.5,
            customdata=custom,
            hovertemplate="%{customdata}<extra></extra>",
            showscale=False,
            xgap=1,
            ygap=1,
        )
    )
    fig.update_xaxes(
        type='linear',
        range=[-0.5, len(days) - 0.5],
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=0,
        title="",
        tickfont=dict(color="#333333", size=10),
        showline=True,
        linecolor=grid_color,
        linewidth=0.8,
        mirror=True,
    )
    fig.update_yaxes(
        range=[n_slots - 0.5, -0.5],
        tickmode="array",
        tickvals=list(range(0, n_slots, 2)),
        ticktext=[f"{h:02d}:00" for h in range(24)],
        title="",
        tickfont=dict(color="#333333", size=10),
        showgrid=False,
        showline=True,
        linecolor=grid_color,
        linewidth=0.8,
        mirror=True,
    )
    fig.update_layout(
        height=max(520, n_slots * 12 + 150),
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=grid_color,
        paper_bgcolor="white",
    )
    return fig