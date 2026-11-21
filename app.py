import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.colors
import plotly.graph_objects as go
import os

st.set_page_config(page_title="我的每日时间轴", layout="wide")

@st.cache_data
def load_data(file):
    df = pd.read_excel(file, header=0) 
    df.columns = [c.strip() for c in df.columns]
    
    df = df[['日期', '开始', '结束', '科目一', '分类', '备注']].dropna(subset=['日期', '开始', '结束'])
    df['日期'] = df['日期'].astype(str).str.strip()
    df['开始'] = df['开始'].astype(str).str.strip()
    df['结束'] = df['结束'].astype(str).str.strip()
    
    df['日期_dt'] = pd.to_datetime(df['日期'], errors='coerce').dt.tz_localize(None)
    df = df.dropna(subset=['日期_dt'])
    
    df['日期_str'] = df['日期_dt'].dt.strftime('%Y-%m-%d')
    
    df['开始时间'] = pd.to_datetime(df['日期_str'] + ' ' + df['开始'], errors='coerce').dt.tz_localize(None)
    df['结束时间'] = pd.to_datetime(df['日期_str'] + ' ' + df['结束'], errors='coerce').dt.tz_localize(None)
    
    df = df.dropna(subset=['开始时间', '结束时间'])
    df.loc[df['结束时间'] < df['开始时间'], '结束时间'] += pd.Timedelta(days=1)
    
    df['科目一'] = df['科目一'].fillna('未命名').astype(str)
    df['分类'] = df['分类'].fillna('其他').astype(str)
    df['备注'] = df['备注'].fillna('').astype(str)
    
    df['时长(小时)'] = (df['结束时间'] - df['开始时间']).dt.total_seconds() / 3600
    
    df['年'] = df['日期_dt'].dt.strftime('%Y')
    df['月'] = df['日期_dt'].dt.strftime('%Y-%m')
    df['月数字'] = df['日期_dt'].dt.month
    df['日数字'] = df['日期_dt'].dt.day
    df['周数字'] = df['日期_dt'].dt.isocalendar().week.astype(int)
    df['周'] = df['日期_dt'].dt.strftime('%Y-W%U')
    
    return df

# 侧边栏：上传文件
st.sidebar.header("📁 数据源")
uploaded_file = st.sidebar.file_uploader("如果网页没有数据，请在此上传 data.xlsx", type=["xlsx"])

# 智能判断
if uploaded_file is not None:
    df = load_data(uploaded_file)
else:
    if os.path.exists('data.xlsx'):
        df = load_data('data.xlsx')
    else:
        st.info("👈 请在左侧上传你的 Excel 数据文件开始使用。")
        st.stop()

# ==========================================
# 【专属调色盘】
# ==========================================
all_subjects = df['科目一'].unique()
palette = plotly.colors.qualitative.Alphabet 
color_map = {subject: palette[i % len(palette)] for i, subject in enumerate(all_subjects)}

color_map["学习"] = "#FF9999"  
color_map["闲暇"] = "#FFCC99"  
color_map["睡觉"] = "#D3D3D3"  
color_map["吃饭"] = "#87CEFA"  
color_map["工作"] = "#1E90FF"  
color_map["其他"] = "#A9A9A9"  
color_map["社交"] = "#FF0000"  
color_map["健身"] = "#32CD32"  
color_map["素养"] = "#D4F1D4"  

# ---------------- 侧边栏交互 ----------------
st.sidebar.header("📅 数据筛选")

display_mode = st.sidebar.radio("查看模式", [
    "📊 时间轴与趋势", 
    "📈 周期汇总总计", 
    "📉 周期分布图"
])

if display_mode in ["📊 时间轴与趋势", "📈 周期汇总总计"]:
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

# ---------------- 主界面展示 ----------------
if display_mode == "📉 周期分布图":
    st.subheader("📉 周期时长分布图")
    
    dist_type = st.radio("选择分布维度", ["按日 (展示单月 1-31 号)", "按周 (展示单年 1-52 周)", "按月 (展示单年 1-12 月)", "按年 (展示所有年份)"], horizontal=True)
    
    subject_options = ["全部（总时长）"] + list(all_subjects)
    selected_subject = st.selectbox("选择要查看的科目", subject_options)
    
    if selected_subject == "全部（总时长）":
        dist_df = df.copy()
        bar_color = "#1E90FF"
    else:
        dist_df = df[df['科目一'] == selected_subject].copy()
        bar_color = color_map.get(selected_subject, "#333")

    if dist_type == "按日 (展示单月 1-31 号)":
        months = sorted(df['月'].unique(), reverse=True)
        sel_month = st.selectbox("请选择月份", months, index=0)
        
        month_df = dist_df[dist_df['月'] == sel_month].groupby('日数字')['时长(小时)'].sum().reset_index()
        all_days = pd.DataFrame({'日数字': range(1, 32)})
        month_df = pd.merge(all_days, month_df, on='日数字', how='left').fillna(0)
        
        fig = go.Figure(go.Bar(
            x=month_df['日数字'], y=month_df['时长(小时)'],
            marker_color=bar_color, text=month_df['时长(小时)'].apply(lambda x: f"{x:.1f}" if x > 0 else ""),
            textposition='outside', marker_line_width=0
        ))
        fig.update_layout(
            title=f"{sel_month} - {selected_subject} 每日时长分布",
            xaxis=dict(title="日期", tickmode='linear', dtick=1), 
            yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    elif dist_type == "按周 (展示单年 1-52 周)":
        years = sorted(df['年'].unique(), reverse=True)
        sel_year = st.selectbox("请选择年份", years, index=0)
        
        year_df = dist_df[dist_df['年'] == sel_year].groupby('周数字')['时长(小时)'].sum().reset_index()
        all_weeks = pd.DataFrame({'周数字': range(1, 54)})
        year_df = pd.merge(all_weeks, year_df, on='周数字', how='left').fillna(0)
        
        fig = go.Figure(go.Scatter(
            x=year_df['周数字'], y=year_df['时长(小时)'],
            mode='lines+markers', line=dict(color=bar_color, width=3),
            fill='tozeroy', fillcolor=bar_color.replace('rgb', 'rgba').replace(')', ', 0.2)') if 'rgb' in bar_color else 'rgba(30, 144, 255, 0.2)'
        ))
        fig.update_layout(
            title=f"{sel_year}年 - {selected_subject} 每周时长趋势",
            xaxis=dict(title="第几周", tickmode='linear', dtick=4), 
            yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    elif dist_type == "按月 (展示单年 1-12 月)":
        years = sorted(df['年'].unique(), reverse=True)
        sel_year = st.selectbox("请选择年份", years, index=0)
        
        year_df = dist_df[dist_df['年'] == sel_year].groupby('月数字')['时长(小时)'].sum().reset_index()
        all_months = pd.DataFrame({'月数字': range(1, 13)})
        year_df = pd.merge(all_months, year_df, on='月数字', how='left').fillna(0)
        
        fig = go.Figure(go.Bar(
            x=year_df['月数字'], y=year_df['时长(小时)'],
            marker_color=bar_color, text=year_df['时长(小时)'].apply(lambda x: f"{x:.1f}" if x > 0 else ""),
            textposition='outside', marker_line_width=0
        ))
        fig.update_layout(
            title=f"{sel_year}年 - {selected_subject} 每月时长分布",
            xaxis=dict(title="月份", tickmode='array', tickvals=list(range(1,13)), ticktext=[f"{i}月" for i in range(1,13)]), 
            yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    else: 
        year_df = dist_df.groupby('年')['时长(小时)'].sum().reset_index()
        
        fig = go.Figure(go.Bar(
            x=year_df['年'], y=year_df['时长(小时)'],
            marker_color=bar_color, text=year_df['时长(小时)'].apply(lambda x: f"{x:.1f}"),
            textposition='outside', marker_line_width=0
        ))
        fig.update_layout(
            title=f"历年 - {selected_subject} 总时长分布",
            xaxis_title="年份", yaxis_title="时长 (小时)", height=400, margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

else:
    if filtered_df.empty:
        st.warning("该时间段没有记录数据。")
    else:
        if display_mode == "📊 时间轴与趋势":
            if view_type == "按日":
                chart_title = f"{selected_val} 的时间轴"
                fig = px.timeline(
                    filtered_df, x_start="开始时间", x_end="结束时间", 
                    y="科目一", color="科目一", text="分类", hover_data=["分类", "备注"], 
                    title=chart_title, color_discrete_map=color_map 
                )
                fig.update_traces(
                    textposition='inside', insidetextanchor='middle',
                    textangle=0, textfont=dict(color='#333333', size=12), cliponaxis=False,
                    marker_line_width=0 
                )
                fig.update_yaxes(autorange="reversed")
                
                for index, row in filtered_df.iterrows():
                    if row['时长(小时)'] * 60 < 30:
                        mid_time = row['开始时间'] + (row['结束时间'] - row['开始时间']) / 2
                        task_color = color_map.get(row['科目一'], 'black') 
                        if task_color in ["#D3D3D3", "#FFCC99", "#FF9999", "#87CEFA", "#A9A9A9", "#D4F1D4"]:
                            task_color = "#333333"
                        fig.add_annotation(
                            x=mid_time, y=row['科目一'], text=row['分类'], showarrow=False, 
                            yshift=20, font=dict(color=task_color, size=12)
                        )
                
                fig.update_layout(
                    xaxis_title=selected_val, yaxis_title="", height=500,
                    xaxis=dict(
                        tickformat="%H:%M", dtick=3600000, 
                        range=[filtered_df['开始时间'].min().replace(hour=0, minute=0, second=0), 
                               filtered_df['开始时间'].max().replace(hour=23, minute=59, second=59)]
                    )
                )
            else:
                chart_title = f"{selected_val} 每日时长统计"
                daily_summary = filtered_df.groupby(['日期_str', '科目一'])['时长(小时)'].sum().reset_index()
                sorted_dates = sorted(daily_summary['日期_str'].unique())
                
                fig = px.bar(
                    daily_summary, x="日期_str", y="时长(小时)", color="科目一",
                    title=chart_title, text_auto='.1f', color_discrete_map=color_map,
                    category_orders={"日期_str": sorted_dates} 
                )
                fig.update_traces(marker_line_width=0)
                fig.update_layout(
                    xaxis_title=selected_val, yaxis_title="累计时长 (小时)", height=500,
                    xaxis=dict(type='category')
                )

            st.plotly_chart(fig, use_container_width=True)

        else:
            st.subheader(f"📈 {selected_val} 累计时长排行")
            
            summary_total = filtered_df.groupby('科目一')['时长(小时)'].sum().reset_index()
            summary_total = summary_total.sort_values(by='时长(小时)', ascending=False)
            
            y_labels = summary_total['科目一'].tolist()
            x_values = summary_total['时长(小时)'].tolist()
            bar_colors = [color_map.get(c, '#333') for c in y_labels]
            text_labels = [f"{v:.1f}h" for v in x_values]
            
            y_labels.reverse()
            x_values.reverse()
            bar_colors.reverse()
            text_labels.reverse()
            
            fig_rank = go.Figure(go.Bar(
                x=x_values, y=y_labels, orientation='h',
                marker_color=bar_colors, text=text_labels,
                textposition='outside', textfont=dict(color='#333333'),
                marker_line_width=0
            ))
            
            fig_rank.update_layout(
                xaxis_title="总时长 (小时)", yaxis_title="", height=400,
                showlegend=False, margin=dict(l=0, r=0, t=30, b=0)
            )
            
            st.plotly_chart(fig_rank, use_container_width=True)
            st.divider() 

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
        
        summary = filtered_df.groupby('科目一').agg(
            总时长=('时长(小时)', 'sum'),
            单次最大=('时长(小时)', 'max'),
            单次最小=('时长(小时)', 'min'),
            单次平均=('时长(小时)', 'mean')
        ).reset_index().sort_values(by='总时长', ascending=False)
        
        for col in ['总时长', '单次最大', '单次最小', '单次平均']:
            summary[col] = summary[col].apply(lambda x: f"{x:.1f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(summary, hide_index=True, use_container_width=True)
        with col2:
            summary_pie = filtered_df.groupby('科目一')['时长(小时)'].sum().reset_index()
            
            fig_pie = px.pie(
                summary_pie, names='科目一', values='时长(小时)', hole=0.4,
                color='科目一', color_discrete_map=color_map 
            )
            fig_pie.update_traces(
                texttemplate='%{percent:.0%}', 
                textposition='inside',
                marker_line_width=0 
            )
            st.plotly_chart(fig_pie, use_container_width=True)