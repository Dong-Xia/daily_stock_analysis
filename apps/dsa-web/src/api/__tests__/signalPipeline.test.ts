import { describe, expect, it } from 'vitest';
import { pickBuyTomorrow, BUY_TOMORROW_STATUSES } from '../signalPipeline';

const row = (status: string) => ({ '股票代码': '002673', '股票名称': 'X', '信号状态': status } as never);

describe('pickBuyTomorrow', () => {
  it('纳入回踩完成与二次放量两类买入态', () => {
    expect(BUY_TOMORROW_STATUSES).toEqual([
      '今日回踩完成→明日买入',
      '二次放量确认→明日买入',
    ]);
    const got = pickBuyTomorrow([
      row('今日回踩完成→明日买入'), row('二次放量确认→明日买入'), row('回踩中(等待两日温和放量)'),
    ]);
    expect(got).toHaveLength(2);
  });
});
