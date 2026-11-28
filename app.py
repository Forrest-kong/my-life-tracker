import os

import numpy as np
import pandas as pd
import plotly.colors
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from heatmap_chart import build_heatmap_figure
from time_logic import build_absolute_times, heatmap_matrix

# 时间轴逻辑改动后把它 +1，强制 st.cache_data 重新计算（否则会继续用旧结果）
DATA_LOGIC_VERSION = 2

st.set_page_config(page_title="个人生活看板", layout="wide")

# ==========================================
# 导航栏
# ==========================================
st.sidebar.title("🧭 导航")
app_mode = st.sidebar.radio("选择模块", ["⏱️ 时间管理", "💰 财务统计"])



# ==========================================
# 数据读取函数
# ==========================================
@st.cache_data
def load_time_data(file, logic_version=DATA_LOGIC_VERSION):
    df = pd.read_excel(file, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[['日期', '开始', '结束', '科目一', '分类', '备注']].dropna(subset=['日期', '开始', '结束'])

    df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
    df = df.dropna(subset=['日期'])
    df['日期_dt'] = df['日期']
    df['日期_str'] = df['日期'].dt.strftime('%Y-%m-%d')

    # 关键：把“以当天开始时刻为锚点”的记录还原成真实物理时间（可多次跨 0 点）
    df = build_absolute_times(df)
    df = df.dropna(subset=['开始时间', '结束时间'])
    df = df[df['结束时间'] > df['开始时间']]

    df['科目一'] = df['科目一'].fillna('未命名').astype(str).str.strip()
    df['分类'] = df['分类'].fillna('其他').astype(str).str.strip()
    df['备注'] = df['备注'].fillna('').astype(str)

    df['时长(小时)'] = (df['结束时间'] - df['开始时间']).dt.total_seconds() / 3600
    df['年'] = df['日期'].dt.strftime('%Y')
    df['月'] = df['日期'].dt.strftime('%Y-%m')
    df['月数字'] = df['日期'].dt.month
    df['日数字'] = df['日期'].dt.day
    df['周数字'] = df['日期'].dt.isocalendar().week.astype(int)
    df['周'] = df['日期'].dt.strftime('%Y-W%U')
    return df.reset_index(drop=True)


@st.cache_data
def load_finance_data(file):
    df = pd.read_excel(file, header=1)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[['日期', '凭证', '科目一', '科目二', '净额', '备注']].dropna(subset=['日期', '净额'])
    df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
    df = df.dropna(subset=['日期'])
    df['净额'] = pd.to_numeric(df['净额'], errors='coerce').fillna(0)

    df['凭证'] = df['凭证'].astype(str).str.strip()
    df['科目一'] = df['科目一'].astype(str).str.strip()
    df['科目二'] = df['科目二'].astype(str).str.strip()
    df['备注'] = df['备注'].fillna('').astype(str)

    df['年'] = df['日期'].dt.strftime('%Y')
    df['月'] = df['日期'].dt.strftime('%Y-%m')
    df['月数字'] = df['日期'].dt.month
    df['日数字'] = df['日期'].dt.day
    df['周数字'] = df['日期'].dt.isocalendar().week.astype(int)
    return df


# ==========================================
# 模块一：⏱️ 时间管理
# ==========================================
if app_mode == "⏱️ 时间管理":
    st.sidebar.header("📁 数据源")
    uploaded_file = st.sidebar.file_uploader("上传时间数据 (data.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df = load_time_data(uploaded_file, DATA_LOGIC_VERSION)
    elif os.path.exists('data.xlsx'):
        df = load_time_data('data.xlsx', DATA_LOGIC_VERSION)
    else:
        st.info("👈 请在左侧上传你的时间数据 Excel。")
        st.stop()

    all_subjects = df['科目一'].unique()
    palette = plotly.colors.qualitative.Alphabet
    color_map = {subject: palette[i % len(palette)] for i, subject in enumerate(all_subjects)}
    color_map.update({"学习": "#FF9999", "闲暇": "#FFCC99", "睡觉": "#D3D3D3", "吃饭": "#87CEFA", "工作": "#1E90FF", "其他": "#A9A9A9", "社交": "#FF0000", "健身": "#32CD32", "素养": "#D4F1D4"})

    st.sidebar.header("📅 数据筛选")
    display_mode = st.sidebar.radio("查看模式", ["📊 时间轴与趋势", "📈 周期汇总总计", "📉 周期分布图"])
    view_type = st.sidebar.radio("时间维度", ["按日", "按周", "按月", "按年"])

    if view_type == "按日":
        dates = sorted(df['日期_str'].unique(), reverse=True)
        selected_val = st.sidebar.selectbox("请选择日期", dates, index=0)
        filtered_df = df[df['日期_str'] == selected_val]
    elif view_type == "按周":
        weeks = sorted(df['周'].unique(), reverse=True)
        selected_val = st.sidebar.selectbox("请选择周", weeks, index=0)
        filtered_df = df[df['周'] == selected_val]
    elif view_type == "按月":
        months = sorted(df['月'].unique(), reverse=True)
        selected_val = st.sidebar.selectbox("请选择月份", months, index=0)
        filtered_df = df[df['月'] == selected_val]
    else:
        years = sorted(df['年'].unique(), reverse=True)
        selected_val = st.sidebar.selectbox("请选择年份", years, index=0)
        filtered_df = df[df['年'] == selected_val]

    if filtered_df.empty:
        st.warning("该时间段没有记录数据。")
    else:
        if display_mode == "📊 时间轴与趋势":
            if view_type == "按日":
                st.subheader(f"{selected_val} 的时间轴")
                fig = px.timeline(filtered_df, x_start="开始时间", x_end="结束时间", y="科目一", color="科目一", text="分类", hover_data=["分类", "备注"], color_discrete_map=color_map)
                fig.update_traces(textposition='inside', insidetextanchor='middle', textangle=0, textfont=dict(color='#333333', size=12), cliponaxis=False, marker_line_width=0)
                fig.update_yaxes(autorange="reversed")
                for _, row in filtered_df.iterrows():
                    if row['时长(小时)'] * 60 < 30:
                        mid_time = row['开始时间'] + (row['结束时间'] - row['开始时间']) / 2
                        task_color = color_map.get(row['科目一'], 'black')
                        if task_color in ["#D3D3D3", "#FFCC99", "#FF9999", "#87CEFA", "#A9A9A9", "#D4F1D4"]:
                            task_color = "#333333"
                        fig.add_annotation(x=mid_time, y=row['科目一'], text=row['分类'], showarrow=False, yshift=20, font=dict(color=task_color, size=12))
                # 自动取数据最小、最大时间，前后扩展30分钟留白
                x_min = filtered_df["开始时间"].min() - pd.Timedelta(minutes=30)
                x_max = filtered_df["结束时间"].max() + pd.Timedelta(minutes=30)
                fig.update_layout(xaxis_title=selected_val, yaxis_title="", height=500, xaxis=dict(tickformat="%H:%M", dtick=3600000, range=[x_min, x_max]))
                st.plotly_chart(fig, use_container_width=True)
            else:
                tab1, tab2, tab3 = st.tabs(["📊 每日时长汇总图", "⏱️ 作息横向分布 (甘特图)", "🔥 作息时间热力图 (推荐)"])

                with tab1:
                    daily_summary = filtered_df.groupby(['日期_str', '科目一'])['时长(小时)'].sum().reset_index()
                    sorted_dates = sorted(daily_summary['日期_str'].unique())
                    fig = px.bar(daily_summary, x="日期_str", y="时长(小时)", color="科目一", title=f"{selected_val} 每日时长汇总", text_auto='.1f', color_discrete_map=color_map, category_orders={"日期_str": sorted_dates})
                    fig.update_traces(marker_line_width=0)
                    fig.update_layout(xaxis_title=selected_val, yaxis_title="累计时长 (小时)", height=500, xaxis=dict(type='category'))
                    st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    st.markdown(f"**{selected_val} 作息分布 (横轴 00:00-24:00，纵轴日期)**")
                    base_date = '2000-01-01'
                    dist_df = filtered_df.copy()
                    start_time_str = dist_df['开始时间'].dt.strftime('%H:%M:%S')
                    end_time_str = dist_df['结束时间'].dt.strftime('%H:%M:%S')
                    dist_df['映射_开始'] = pd.to_datetime(base_date + ' ' + start_time_str)
                    dist_df['映射_结束'] = pd.to_datetime(base_date + ' ' + end_time_str)
                    dist_df.loc[dist_df['映射_结束'] < dist_df['映射_开始'], '映射_结束'] += pd.Timedelta(days=1)
                    dist_df['展示日期'] = dist_df['日期_str']

                    fig_dist = px.timeline(
                        dist_df, x_start="映射_开始", x_end="映射_结束",
                        y="展示日期", color="科目一",
                        hover_data=["科目一", "分类", "备注"],
                        color_discrete_map=color_map,
                    )
                    fig_dist.update_traces(textposition='inside', textangle=0, textfont=dict(color='#333333', size=10), marker_line_width=0)
                    fig_dist.update_yaxes(autorange="reversed", title="")
                    fig_dist.update_layout(
                        xaxis_title="时间", height=max(400, len(dist_df['展示日期'].unique()) * 30 + 150),
                        xaxis=dict(tickformat="%H:%M", dtick=7200000, range=[pd.to_datetime(base_date + ' 00:00:00'), pd.to_datetime(base_date + ' 23:59:59')]),
                        margin=dict(l=0, r=0, t=20, b=0)
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)

                with tab3:
                    st.markdown(f"**{selected_val} 作息热力图 (纵轴 00:00-24:00，横轴自然日，颜色代表科目)**")
                    st.caption("按真实物理时间以 0 点为界切分：一晚跨过 0 点，0 点前后分别落在两天里；白色格子表示该时段没记录。")

                    # 显示范围取自当前筛选周期；但取数用全量 df，保证月初凌晨能拿到上一天的“尾巴”
                    range_start = filtered_df['日期_dt'].min().normalize()
                    range_end = filtered_df['日期_dt'].max().normalize() + pd.Timedelta(days=1)
                    days = pd.date_range(range_start, range_end - pd.Timedelta(days=1), freq='D')

                    subset = df[(df['结束时间'] > range_start) & (df['开始时间'] < range_end)]
                    matrix, _ = heatmap_matrix(subset, days, slot_minutes=30)

                    if matrix.notna().to_numpy().any():
                        fig_hm = build_heatmap_figure(matrix, days, color_map, list(all_subjects), n_slots=len(matrix))
                        st.plotly_chart(fig_hm, use_container_width=True)
                    else:
                        st.info("无有效数据生成热力图。")

        elif display_mode == "📈 周期汇总总计":
            st.subheader(f"📈 {selected_val} 累计时长排行")
            summary_total = filtered_df.groupby('科目一')['时长(小时)'].sum().reset_index().sort_values(by='时长(小时)', ascending=False)
            y_labels = summary_total['科目一'].tolist()
            x_values = summary_total['时长(小时)'].tolist()
            bar_colors = [color_map.get(c, '#333') for c in y_labels]
            text_labels = [f"{v:.1f}h" for v in x_values]
            y_labels.reverse(); x_values.reverse(); bar_colors.reverse(); text_labels.reverse()
            fig_rank = go.Figure(go.Bar(x=x_values, y=y_labels, orientation='h', marker_color=bar_colors, text=text_labels, textposition='outside', textfont=dict(color='#333333'), marker_line_width=0))
            fig_rank.update_layout(xaxis_title="总时长 (小时)", yaxis_title="", height=400, showlegend=False, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_rank, use_container_width=True)
            st.divider()

        else:  # 周期分布图
            st.subheader("📉 周期时长分布图")
            dist_type = st.radio("选择分布维度", ["按日 (单月)", "按周 (单年)", "按月 (单年)", "按年 (历年)"], horizontal=True)
            subject_options = ["全部（总时长）"] + list(all_subjects)
            selected_subject = st.selectbox("选择要查看的科目", subject_options)
            if selected_subject == "全部（总时长）":
                dist_df = df.copy(); bar_color = "#1E90FF"
            else:
                dist_df = df[df['科目一'] == selected_subject].copy(); bar_color = color_map.get(selected_subject, "#333")

            if dist_type == "按日 (单月)":
                sel_month = st.selectbox("请选择月份", sorted(df['月'].unique(), reverse=True), index=0)
                month_df = dist_df[dist_df['月'] == sel_month].groupby('日数字')['时长(小时)'].sum().reset_index().sort_values('日数字')
                fig = go.Figure(go.Bar(x=month_df['日数字'], y=month_df['时长(小时)'], marker_color=bar_color, text=month_df['时长(小时)'].apply(lambda x: f"{x:.1f}"), textposition='outside', marker_line_width=0))
                fig.update_layout(title=f"{sel_month} - {selected_subject} 每日时长分布", xaxis=dict(title="日期", type='category'), yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            elif dist_type == "按周 (单年)":
                sel_year = st.selectbox("请选择年份", sorted(df['年'].unique(), reverse=True), index=0)
                year_df = dist_df[dist_df['年'] == sel_year].groupby('周数字')['时长(小时)'].sum().reset_index().sort_values('周数字')
                fig = go.Figure(go.Scatter(x=year_df['周数字'], y=year_df['时长(小时)'], mode='lines+markers', line=dict(color=bar_color, width=3), fill='tozeroy', fillcolor='rgba(30, 144, 255, 0.2)'))
                fig.update_layout(title=f"{sel_year}年 - {selected_subject} 每周时长趋势", xaxis=dict(title="第几周", type='category'), yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            elif dist_type == "按月 (单年)":
                sel_year = st.selectbox("请选择年份", sorted(df['年'].unique(), reverse=True), index=0)
                year_df = dist_df[dist_df['年'] == sel_year].groupby('月数字')['时长(小时)'].sum().reset_index().sort_values('月数字')
                fig = go.Figure(go.Bar(x=year_df['月数字'], y=year_df['时长(小时)'], marker_color=bar_color, text=year_df['时长(小时)'].apply(lambda x: f"{x:.1f}"), textposition='outside', marker_line_width=0))
                fig.update_layout(title=f"{sel_year}年 - {selected_subject} 每月时长分布", xaxis=dict(title="月份", type='category'), yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                year_df = dist_df.groupby('年')['时长(小时)'].sum().reset_index()
                fig = go.Figure(go.Bar(x=year_df['年'], y=year_df['时长(小时)'], marker_color=bar_color, text=year_df['时长(小时)'].apply(lambda x: f"{x:.1f}"), textposition='outside', marker_line_width=0))
                fig.update_layout(title=f"历年 - {selected_subject} 总时长分布", xaxis=dict(title="年份", type='category'), yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

        # 底部统计表 & 饼图
        st.subheader(f"📊 {selected_val} 时间统计")
        total_time = filtered_df['时长(小时)'].sum()
        avg_time = filtered_df['时长(小时)'].mean()
        max_row = filtered_df.loc[filtered_df['时长(小时)'].idxmax()]
        min_row = filtered_df.loc[filtered_df['时长(小时)'].idxmin()]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("当前周期总时长", f"{total_time:.1f} h")
        m2.metric("单次平均时长", f"{avg_time:.1f} h")
        m3.metric("最长单次记录", f"{max_row['时长(小时)']:.1f} h", f"科目：{max_row['科目一']}", delta_color="off")
        m4.metric("最短单次记录", f"{min_row['时长(小时)']:.1f} h", f"科目：{min_row['科目一']}", delta_color="off")
        st.write("---")
        summary = filtered_df.groupby('科目一').agg(总时长=('时长(小时)', 'sum'), 单次最大=('时长(小时)', 'max'), 单次最小=('时长(小时)', 'min'), 单次平均=('时长(小时)', 'mean')).reset_index().sort_values(by='总时长', ascending=False)
        for col in ['总时长', '单次最大', '单次最小', '单次平均']:
            summary[col] = summary[col].apply(lambda x: f"{x:.1f}")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(summary, hide_index=True, use_container_width=True)
        with col2:
            summary_pie = filtered_df.groupby('科目一')['时长(小时)'].sum().reset_index()
            fig_pie = px.pie(summary_pie, names='科目一', values='时长(小时)', hole=0.4, color='科目一', color_discrete_map=color_map)
            fig_pie.update_traces(texttemplate='%{percent:.0%}', textposition='inside', marker_line_width=0)
            fig_pie.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), margin=dict(b=50))
            st.plotly_chart(fig_pie, use_container_width=True)


# ==========================================
# 模块二：💰 财务统计 (资金增长看板)
# ==========================================
elif app_mode == "💰 财务统计":
    st.sidebar.header("📁 数据源")
    uploaded_file = st.sidebar.file_uploader("上传财务数据 (finance.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df_fin = load_finance_data(uploaded_file)
    elif os.path.exists('finance.xlsx'):
        df_fin = load_finance_data('finance.xlsx')
    else:
        st.info("👈 请在左侧上传你的财务 Excel。")
        st.stop()

    st.sidebar.header("📅 趋势对比筛选")
    fin_view_type = st.sidebar.radio("统计维度", ["按年汇总", "按月趋势", "按周趋势", "按日趋势"])

    if fin_view_type == "按年汇总":
        compare_df = df_fin.copy()
        x_col = '年'
        x_title = "全部"
    elif fin_view_type == "按月趋势":
        years = sorted(df_fin['年'].unique().tolist(), reverse=True)
        sel_year = st.sidebar.selectbox("选择年份", years, index=0)
        compare_df = df_fin[df_fin['年'] == sel_year]
        x_col = '月数字'
        x_title = f"{sel_year}"
    elif fin_view_type == "按周趋势":
        years = sorted(df_fin['年'].unique().tolist(), reverse=True)
        sel_year = st.sidebar.selectbox("选择年份", years, index=0)
        compare_df = df_fin[df_fin['年'] == sel_year]
        x_col = '周数字'
        x_title = f"{sel_year}"
    else:
        months = sorted(df_fin['月'].unique().tolist(), reverse=True)
        sel_month = st.sidebar.selectbox("选择月份", months, index=0)
        compare_df = df_fin[df_fin['月'] == sel_month]
        x_col = '日数字'
        x_title = f"{sel_month.replace('-', '年')}月"

    # --- 财务总览卡片 ---
    exp_data = compare_df[compare_df['凭证'].str.contains('支出')]
    inc_data = compare_df[compare_df['凭证'].str.contains('收入')]

    total_expense = abs(exp_data['净额'].sum())
    total_income = inc_data['净额'].sum()
    net_balance = total_income - total_expense

    if total_income > 0:
        balance_ratio = (net_balance / total_income) * 100
    else:
        balance_ratio = 0.0

    fmt_exp = f"¥ {int(round(total_expense)):,}"
    fmt_inc = f"¥ {int(round(total_income)):,}"
    fmt_net = f"¥ {int(round(net_balance)):,}"
    net_color = "red" if net_balance < 0 else "green"
    ratio_color = "red" if balance_ratio < 0 else "green"

    st.subheader(f"💰 {fin_view_type} 财务总览")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总支出", fmt_exp)
    c2.metric("总收入", fmt_inc)

    with c3:
        st.markdown(
            f"""
            <div style="margin-bottom: 0.5rem; font-size: 0.875rem; color: rgb(49, 51, 63);">净结余 (资金总增长)</div>
            <div style="font-size: 2.25rem; font-weight: 600; color: {net_color}; margin-bottom: 0; line-height: 1.2;">
                {fmt_net}
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:
        st.markdown(
            f"""
            <div style="margin-bottom: 0.5rem; font-size: 0.875rem; color: rgb(49, 51, 63);">结余率 (占总收入)</div>
            <div style="font-size: 2.25rem; font-weight: 600; color: {ratio_color}; margin-bottom: 0; line-height: 1.2;">
                {balance_ratio:.1f}%
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("---")

    # ==========================================
    # 核心图表：资金增长趋势
    # ==========================================
    st.subheader("📈 资金增长趋势分析")

    exp_grouped = exp_data.groupby(x_col)['净额'].sum().abs()
    inc_grouped = inc_data.groupby(x_col)['净额'].sum()

    trend_df = pd.DataFrame({'支出': exp_grouped, '收入': inc_grouped}).fillna(0).reset_index()
    trend_df['净结余'] = trend_df['收入'] - trend_df['支出']
    trend_df = trend_df.sort_values(by=x_col)

    trend_df['x_label'] = trend_df[x_col].astype(int).astype(str)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**每期净结余 (绿增长 / 红缩水)**")
        bar_colors = ['#32CD32' if val >= 0 else '#FF0000' for val in trend_df['净结余']]

        text_labels_net = [f"{abs(int(round(val))):,}" if val != 0 else "" for val in trend_df['净结余']]
        text_colors_net = ['red' if val < 0 else '#333333' for val in trend_df['净结余']]

        fig_net = go.Figure(go.Bar(
            x=trend_df['x_label'], y=trend_df['净结余'],
            marker_color=bar_colors,
            text=text_labels_net,
            textposition='outside',
            cliponaxis=False,
            textfont=dict(color=text_colors_net)
        ))
        fig_net.update_layout(
            xaxis=dict(title=x_title, type='category'), yaxis_title="净结余 (元)", height=400,
            margin=dict(l=0, r=0, t=20, b=0)
        )
        fig_net.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_net, use_container_width=True)

    with col_g2:
        st.markdown("**累计资金池增长曲线**")
        trend_df['累计资金池'] = trend_df['净结余'].cumsum()

        text_labels_cum = [f"{abs(int(round(val))):,}" for val in trend_df['累计资金池']]
        text_colors_cum = ['red' if val < 0 else '#333333' for val in trend_df['累计资金池']]

        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=trend_df['x_label'], y=trend_df['累计资金池'],
            mode='lines+markers+text',
            line=dict(color='#1E90FF', width=3),
            fill='tozeroy', fillcolor='rgba(30, 144, 255, 0.1)',
            text=text_labels_cum,
            textposition="top center",
            textfont=dict(color=text_colors_cum)
        ))
        fig_cum.update_layout(
            xaxis=dict(title=x_title, type='category'), yaxis_title="累计资产 (元)", height=400,
            margin=dict(l=0, r=0, t=20, b=0)
        )
        fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_cum, use_container_width=True)

    st.write("---")

    # ==========================================
    # 收支细节对比
    # ==========================================
    st.subheader(f"📈 {fin_view_type} 收支流水对比")
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=trend_df['x_label'], y=trend_df['支出'], name='支出', marker_color='#FF9999',
        text=trend_df['支出'].apply(lambda x: f"{int(round(x)):,}" if x > 0 else ""),
        textposition='outside', cliponaxis=False
    ))
    fig_trend.add_trace(go.Bar(
        x=trend_df['x_label'], y=trend_df['收入'], name='收入', marker_color='#1E90FF',
        text=trend_df['收入'].apply(lambda x: f"{int(round(x)):,}" if x > 0 else ""),
        textposition='outside', cliponaxis=False
    ))
    fig_trend.update_layout(
        barmode='group', xaxis=dict(title=x_title, type='category'), yaxis_title="金额 (元)", height=350,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.write("---")

    # --- 图表区域 ---
    st.subheader("🍰 财务分类分析 (基于上方筛选)")
    col_chart1, col_chart2, col_chart3 = st.columns(3)

    with col_chart1:
        st.markdown("**收支平衡占比**")
        balance_data = pd.DataFrame({
            '类别': ['总支出', '总收入'],
            '金额': [total_expense, total_income]
        })

        if total_expense > 0 or total_income > 0:
            fig_balance = px.pie(
                balance_data, names='类别', values='金额', hole=0.5,
                color='类别', color_discrete_map={'总支出': '#FF9999', '总收入': '#1E90FF'}
            )
            fig_balance.update_traces(texttemplate='%{percent:.1%}', textposition='inside', marker_line_width=0)

            fig_balance.update_layout(
                margin=dict(l=0, r=0, t=20, b=60),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
                annotations=[
                    dict(
                        text=f"{balance_ratio:.1f}%",
                        x=0.5, y=0.5,
                        font=dict(size=28, color='#1E90FF' if net_balance >= 0 else '#FF0000'),
                        showarrow=False
                    ),
                    dict(
                        text=x_title, xref="paper", yref="paper", x=0.5, y=-0.1,
                        showarrow=False, font=dict(size=14, color="gray")
                    )
                ]
            )
            st.plotly_chart(fig_balance, use_container_width=True)
        else:
            st.info("无记录")

    with col_chart2:
        st.markdown("**支出分类占比**")
        if not exp_data.empty:
            exp_data_copy = exp_data.copy()
            exp_data_copy['绝对金额'] = exp_data_copy['净额'].abs()
            pie_data = exp_data_copy.groupby('科目二')['绝对金额'].sum().reset_index()
            fig_pie = px.pie(pie_data, names='科目二', values='绝对金额', hole=0.4)
            fig_pie.update_traces(texttemplate='%{percent:.1%}', textposition='inside', marker_line_width=0)

            fig_pie.update_layout(
                margin=dict(l=0, r=0, t=20, b=60),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
                annotations=[
                    dict(
                        text=x_title, xref="paper", yref="paper", x=0.5, y=-0.1,
                        showarrow=False, font=dict(size=14, color="gray")
                    )
                ]
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("无支出记录")

    with col_chart3:
        st.markdown("**各月份支出趋势**")
        if not exp_data.empty:
            exp_data_copy = exp_data.copy()
            exp_data_copy['绝对金额'] = exp_data_copy['净额'].abs()
            monthly_line = exp_data_copy.groupby('月')['绝对金额'].sum().reset_index().sort_values('月')
            fig_line = px.line(monthly_line, x='月', y='绝对金额', markers=True)
            fig_line.update_layout(xaxis=dict(type='category'), yaxis_title="支出金额", height=300, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("无支出记录")

    st.write("---")

    # --- 账单明细 ---
    st.subheader("📝 账单明细")

    detail_df = compare_df[['日期', '凭证', '科目一', '科目二', '净额', '备注']].sort_values('日期', ascending=False)
    detail_df['日期'] = detail_df['日期'].dt.strftime('%Y-%m-%d')

    styled_df = detail_df.style.format({'净额': lambda x: f"{abs(int(round(x))):,}"}).map(
        lambda x: 'color: red; font-weight: bold;' if isinstance(x, (int, float)) and x < 0 else '',
        subset=['净额']
    )

    st.dataframe(styled_df, hide_index=True, use_container_width=True)
