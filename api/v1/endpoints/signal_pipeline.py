# -*- coding: utf-8 -*-
"""
信号链多时段流水线 API
POST /signal-pipeline/run               — 启动流水线
GET  /signal-pipeline/status            — 查询运行进度
GET  /signal-pipeline/results           — 查询筛选结果
GET  /signal-pipeline/fundamental-filter — 信号链结果与基本面通过名单取交集
GET  /signal-pipeline/download          — 下载每日分析 Excel
"""

import json
import logging
import os
import subprocess
import threading
from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

STOCK_DATA_DIR = os.getenv('SIGNAL_STOCK_DATA_DIR', '/Users/zhangze/stockData')
PIPELINE_SCRIPT = os.path.join(STOCK_DATA_DIR, 'dsa_signal', 'run_pipeline.py')
STATUS_FILE = os.path.join(STOCK_DATA_DIR, '_pipeline_status.json')

TIMEFRAMES = ['daily', '5min', '15min', '30min']
TIMEFRAME_LABELS = {'daily': '日线', '5min': '5分钟', '15min': '15分钟', '30min': '30分钟'}

# 运行状态
_running = {'thread': None, 'date': None}


class PipelineRunRequest(BaseModel):
    date: str = ''


class PipelineStatus(BaseModel):
    running: bool
    date: str = ''
    step: int = 0
    total: int = 5
    label: str = ''
    state: str = ''
    detail: str = ''


class SignalResults(BaseModel):
    date: str
    timeframe: str
    timeframe_label: str
    count: int
    rows: list


def _load_signal_df(date: str, timeframe: str) -> pd.DataFrame:
    """读取信号链 CSV(fundflow 变体优先), 不存在时 404。"""
    key = date.replace('-', '')
    suffix = '' if timeframe == 'daily' else f'_{timeframe}'
    fund_file = os.path.join(STOCK_DATA_DIR, f'signal_chain_{key}{suffix}_fundflow.csv')
    chain_file = os.path.join(STOCK_DATA_DIR, f'signal_chain_{key}{suffix}.csv')

    src = fund_file if os.path.exists(fund_file) else chain_file
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=f'未找到 {date} {TIMEFRAME_LABELS[timeframe]} 信号链')

    df = pd.read_csv(src, dtype=str).fillna('')
    # 重命名列以便前端统一处理
    return df.rename(columns={'当日主力占比%': '当日主力占比'})


def _run_pipeline(trade_date: str):
    """在后台线程执行流水线"""
    try:
        r = subprocess.run(
            ['python3', '-m', 'dsa_signal.run_pipeline', trade_date],
            cwd=STOCK_DATA_DIR,
            capture_output=True, text=True,
            timeout=1800,
        )
        if r.returncode != 0:
            logger.error('Pipeline failed: %s', r.stderr[-500:] if r.stderr else '')
        else:
            logger.info('Pipeline completed: %s', trade_date)
    except subprocess.TimeoutExpired:
        logger.error('Pipeline timed out: %s', trade_date)
    except Exception as e:
        logger.error('Pipeline error: %s', e)
    finally:
        _running['thread'] = None
        _running['date'] = None


@router.post('/run', summary='启动信号链流水线')
async def run_pipeline(req: PipelineRunRequest = PipelineRunRequest()):
    if _running['thread'] and _running['thread'].is_alive():
        raise HTTPException(status_code=409, detail='流水线正在运行中, 请等待完成')

    trade_date = req.date or date.today().isoformat()
    t = threading.Thread(target=_run_pipeline, args=(trade_date,), daemon=True)
    _running['thread'] = t
    _running['date'] = trade_date
    t.start()
    return {'message': f'流水线已启动: {trade_date}', 'date': trade_date}


@router.get('/status', response_model=PipelineStatus, summary='查询流水线进度')
def get_status():
    # 同步 def：文件读取交给 FastAPI 线程池，避免阻塞事件循环
    if not _running['thread'] or not _running['thread'].is_alive():
        # 尝试读取最后状态
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE) as f:
                s = json.load(f)
            return PipelineStatus(
                running=False, date=_running['date'] or '',
                step=s.get('step', 0), total=s.get('total', 5),
                label=s.get('label', ''), state=s.get('state', ''),
                detail=s.get('detail', ''),
            )
        return PipelineStatus(running=False)

    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f:
            s = json.load(f)
        return PipelineStatus(
            running=True, date=_running['date'] or '',
            step=s.get('step', 0), total=s.get('total', 5),
            label=s.get('label', ''), state=s.get('state', ''),
            detail=s.get('detail', ''),
        )
    return PipelineStatus(running=True, date=_running['date'] or '')


@router.get('/results', summary='查询信号链结果')
def get_results(
    date: str = Query(..., description='交易日 YYYY-MM-DD'),
    timeframe: str = Query('daily', description='时段: daily/5min/15min/30min'),
):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f'无效时段: {timeframe}')

    df = _load_signal_df(date, timeframe)

    return SignalResults(
        date=date,
        timeframe=timeframe,
        timeframe_label=TIMEFRAME_LABELS[timeframe],
        count=len(df),
        rows=df.to_dict(orient='records'),
    )


class FundamentalFilterResults(BaseModel):
    date: str
    timeframe: str
    timeframe_label: str
    quarter: str
    total: int
    matched: int
    rows: list


@router.get('/fundamental-filter', summary='信号链结果与基本面通过名单取交集')
def get_fundamental_filter(
    date: str = Query(..., description='交易日 YYYY-MM-DD'),
    timeframe: str = Query('daily', description='时段: daily/5min/15min/30min'),
):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f'无效时段: {timeframe}')

    from src.services.fundamental_screener import FundamentalScreener

    df = _load_signal_df(date, timeframe)
    quarter = FundamentalScreener._resolve_latest_quarter()
    try:
        pass_map = FundamentalScreener().get_pass_map(quarter)
    except Exception as e:
        logger.error('基本面通过名单获取失败: %s', e)
        raise HTTPException(status_code=502, detail=f'财报数据获取失败: {e}')

    rows = df.to_dict(orient='records')
    matched_rows = []
    for row in rows:
        code = str(row.get('股票代码', '')).strip()
        fund = pass_map.get(code)
        if fund is None:
            continue
        matched_rows.append({
            **row,
            '营收同比%': f"{fund['revenue_yoy']:.1f}",
            '利润同比%': f"{fund['profit_yoy']:.1f}",
            '净利润(亿)': f"{fund['net_profit'] / 1e8:.2f}",
            '基本面评分': f"{fund['composite_score']:.1f}",
        })

    return FundamentalFilterResults(
        date=date,
        timeframe=timeframe,
        timeframe_label=TIMEFRAME_LABELS[timeframe],
        quarter=quarter,
        total=len(rows),
        matched=len(matched_rows),
        rows=matched_rows,
    )


@router.get('/download', summary='下载信号链 Excel')
def download_excel(date: str = Query(...)):
    key = date.replace('-', '')
    excel_file = os.path.join(STOCK_DATA_DIR, f'每日分析_{key}.xlsx')
    if not os.path.exists(excel_file):
        raise HTTPException(status_code=404, detail=f'未找到 {date} Excel 文件')
    from fastapi.responses import FileResponse
    return FileResponse(excel_file, filename=f'每日分析_{key}.xlsx')
