import { describe, expect, test } from 'vitest';
import { buyVerdict } from '../buyVerdict';

describe('buyVerdict', () => {
  test('各档位映射为买入语义', () => {
    expect(buyVerdict('🟢').label).toBe('技术+筹码双确认 · 可买');
    expect(buyVerdict('⚪').label).toBe('量化做T假象 · 可正常买');
    expect(buyVerdict('🟡').label).toBe('筹码不稳 · 轻仓/观察');
    expect(buyVerdict('🟠').label).toBe('底筹连降 · 诱多风险，谨慎');
    expect(buyVerdict('🔴').label).toBe('主力派发 · 放弃明日买入');
    expect(buyVerdict('—').label).toBe('数据不足 · 无法判断');
  });

  test('highProfitRisk 追加获利盘风险提示', () => {
    expect(buyVerdict('🟢', true).label).toBe('技术+筹码双确认 · 可买｜⚠️获利盘>90%');
    expect(buyVerdict('🔴', true).label).toContain('⚠️获利盘>90%');
  });

  test('未知档位回退且不抛错', () => {
    const v = buyVerdict('★');
    expect(v.label).toBe('无法判断');
    expect(v.cls).toBeTruthy();
  });

  test('每个档位都返回配色 cls', () => {
    for (const lv of ['🔴', '🟠', '🟡', '⚪', '🟢', '—']) {
      expect(buyVerdict(lv).cls).toMatch(/border|text|bg/);
    }
  });
});
