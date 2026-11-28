"""
把“以睡觉开始时间为锚点”的记录，还原成真实物理时间（含多次跨 0 点），
再按自然日 00:00-24:00 切成半小时格子，供热力图使用。

记录表要求列：日期_str / 开始 / 结束 / 科目一
"""

from __future__ import annotations

import pandas as pd

SLOT_MINUTES = 30
ANCHOR_HOUR = 18      # 首条记录 >= 18:00 视为“前一天晚上开始”
WRAP_HOURS = 6        # 开始时刻比上一条倒退超过 6 小时，判定为跨过 0 点


def parse_clock(value):
    """把 7:30 / 07:30:00 / 24:00 / Excel 时间小数 解析成 Timedelta。"""
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timedelta):
        return value
    try:
        if pd.isna(value):
            return pd.NaT
    except (TypeError, ValueError):
        pass

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if 0 <= v < 1:
            return pd.Timedelta(days=v)
        if 0 <= v < 24:
            return pd.Timedelta(hours=v)
        return pd.NaT

    s = str(value).strip().replace("：", ":")
    if not s or s.lower() in {"nan", "nat", "none"}:
        return pd.NaT

    parts = s.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
        second = int(float(parts[2])) if len(parts) > 2 and parts[2] != "" else 0
    except (ValueError, TypeError):
        return pd.NaT

    if hour < 0 or not (0 <= minute < 60) or not (0 <= second < 60):
        return pd.NaT
    return pd.Timedelta(hours=hour, minutes=minute, seconds=second)


def build_absolute_times(df, anchor_hour=ANCHOR_HOUR, wrap_hours=WRAP_HOURS):
    """
    df 需含：日期_str(YYYY-MM-DD)、开始、结束、科目一，且同一“逻辑日”的行连在一起。

    逻辑：
    1. 首条记录是“睡觉”时，沿用睡觉锚点（>=18:00 算前一天晚上）。
       首条不是睡觉时，先按标签当天排，再按“0 点前后各占多久”整组平移：
       - 没跨 0 点：就从标签当天开始；
       - 跨 1 个 0 点：0 点前短、0 点后长 => 从前一天晚上开始；否则从当天开始；
       - 跨 2 个 0 点：从前一天晚上开始（中间正好是标签那天的 24 小时）。
    2. 组内按行序推进；开始时刻比上一条倒退超过 6 小时 => 跨过了一个 0 点，日期 +1。
    3. 任何记录都不能早于这个逻辑日自己的起点（首条记录）。如果早于起点，
       说明它其实是第二天（例如 22:00 一觉睡到次日 17:00，17:00 的记录不该算前一天）。
    4. 单条记录若结束 <= 开始，则结束日期 +1（记录本身跨 0 点）。
    """
    out = df.copy().reset_index(drop=True)
    out["_order"] = range(len(out))
    out["_开始_td"] = out["开始"].map(parse_clock)
    out["_结束_td"] = out["结束"].map(parse_clock)
    out["_日期"] = pd.to_datetime(out["日期_str"], errors="coerce").dt.normalize()

    starts = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
    ends = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
    one_day = pd.Timedelta(days=1)
    wrap_limit = pd.Timedelta(hours=wrap_hours)
    tol = pd.Timedelta(minutes=1)

    for date_str in out["日期_str"].drop_duplicates():
        idx = out.index[out["日期_str"] == date_str]
        base_day = out.at[idx[0], "_日期"]
        first_clock = out.at[idx[0], "_开始_td"]
        if pd.isna(base_day) or pd.isna(first_clock):
            continue

        # 首条记录是“睡觉”：沿用原来的睡觉锚点（>=18:00 算前一天晚上）。
        # 首条不是睡觉：先按标签当天排，最后再用 0 点前后时长决定整组平移。
        first_is_sleep = str(out.at[idx[0], "科目一"]).strip() == "睡觉"
        if first_is_sleep:
            anchor = base_day - one_day if first_clock >= pd.Timedelta(hours=anchor_hour) else base_day
            use_span_anchor = False
        else:
            anchor = base_day
            use_span_anchor = True

        offset_days = 0
        origin = None
        prev_end = None
        prev_clock = None
        first_start = None
        for i in idx:
            clock = out.at[i, "_开始_td"]
            end_clock = out.at[i, "_结束_td"]
            if pd.isna(clock) or pd.isna(end_clock):
                continue

            start_abs = anchor + pd.Timedelta(days=offset_days) + clock
            if origin is None:
                origin = start_abs
                first_start = start_abs

            # 不能早于逻辑日起点：22:00 睡到次日 17:00 时，17:00 必须算第二天
            while start_abs < origin - tol:
                offset_days += 1
                start_abs = anchor + pd.Timedelta(days=offset_days) + clock

            if (
                prev_end is not None
                and start_abs < prev_end - tol
                and prev_clock is not None
                and prev_clock - clock > wrap_limit
            ):
                offset_days += 1
                start_abs = anchor + pd.Timedelta(days=offset_days) + clock

            end_abs = anchor + pd.Timedelta(days=offset_days) + end_clock
            while end_abs < start_abs:
                end_abs += one_day

            starts.at[i] = start_abs
            ends.at[i] = end_abs
            prev_end = end_abs
            prev_clock = clock

        # ---- 首条不是睡觉：按“0 点前后时长”决定整组落在哪一天 ----
        if use_span_anchor:
            group_ends = ends.loc[idx].dropna()
            if first_start is None or group_ends.empty:
                continue
            last_end = group_ends.max()
            total_minutes = (last_end - first_start).total_seconds() / 60
            s0 = (first_start - first_start.normalize()).total_seconds() / 60
            midnights = int((s0 + total_minutes) // 1440)

            shift = 0
            if midnights >= 2:
                shift = -1
            elif midnights == 1:
                before = 1440 - s0          # 0 点之前这一段
                after = total_minutes - before
                if before < after:
                    shift = -1
                elif before == after and s0 >= anchor_hour * 60:
                    shift = -1

            if shift:
                starts.loc[idx] = starts.loc[idx] + pd.Timedelta(days=shift)
                ends.loc[idx] = ends.loc[idx] + pd.Timedelta(days=shift)

    out["开始时间"] = starts
    out["结束时间"] = ends
    out["时长(小时)"] = (ends - starts).dt.total_seconds() / 3600
    return out


def build_slot_table(records, slot_minutes=SLOT_MINUTES):
    """把每条记录按真实时间铺到 30 分钟格子里，返回 (日期, 时段, 科目一, 覆盖秒)。"""
    slot = pd.Timedelta(minutes=slot_minutes)
    rows = []
    for _, row in records.iterrows():
        start, end = row["开始时间"], row["结束时间"]
        if pd.isna(start) or pd.isna(end) or end <= start:
            continue
        t = start
        while t < end:
            slot_start = t.floor(f"{slot_minutes}min")
            slot_end = slot_start + slot
            seg_end = min(end, slot_end)
            rows.append(
                {
                    "日期": slot_start.normalize(),
                    "时段": int((slot_start - slot_start.normalize()) / slot),
                    "科目一": row["科目一"],
                    "覆盖秒": (seg_end - t).total_seconds(),
                    "_order": int(row["_order"]),
                }
            )
            t = seg_end

    if not rows:
        return pd.DataFrame(columns=["日期", "时段", "科目一", "覆盖秒", "_order"])
    return pd.DataFrame(rows)


def pick_slot_subjects(table):
    """同一个格子里若有多条记录重叠，取覆盖时间最长的；一样长取更晚录入的。"""
    if table.empty:
        return table
    agg = (
        table.groupby(["日期", "时段", "科目一"], as_index=False)
        .agg(覆盖秒=("覆盖秒", "sum"), _order=("_order", "max"))
        .sort_values(["日期", "时段", "覆盖秒", "_order"])
    )
    return agg.groupby(["日期", "时段"], as_index=False).tail(1)


def heatmap_matrix(records, days, slot_minutes=SLOT_MINUTES):
    """返回 (matrix, best)。matrix 行=时段序号，列=自然日，值=科目一/NaN。"""
    best = pick_slot_subjects(build_slot_table(records, slot_minutes))
    n_slots = 24 * 60 // slot_minutes
    matrix = pd.DataFrame(
        index=range(n_slots),
        columns=pd.Index(list(days), name="日期"),
        dtype=object,
    )
    if not best.empty:
        for _, r in best.iterrows():
            if r["日期"] in matrix.columns:
                matrix.at[r["时段"], r["日期"]] = r["科目一"]
    return matrix, best
