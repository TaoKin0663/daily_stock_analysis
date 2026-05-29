import React, { useCallback, useEffect, useState } from 'react';
import { Coins, History } from 'lucide-react';
import { Card } from '@heroui/react/card';
import { paymentApi, type DeductionHistoryItem, type DepositHistoryItem } from '../api/payment';
import { EmptyState } from '../components/common';
import { DepositDialog } from '../components/payment/DepositDialog';
import { useCreditStore } from '../stores/creditStore';

const PaymentPage: React.FC = () => {
  const {
    balance, lifetimeCredits, creditsPerDollar, creditsPer1kTokens,
    claimedToday, claiming, claimError,
    initialize, refreshBalance, claimDailyCredits,
  } = useCreditStore();

  const [deposits, setDeposits] = useState<DepositHistoryItem[]>([]);
  const [deductions, setDeductions] = useState<DeductionHistoryItem[]>([]);
  const [showDeposit, setShowDeposit] = useState(false);

  useEffect(() => {
    document.title = '积分 - DSA';
    void initialize();
  }, [initialize]);

  const loadHistory = useCallback(async (cancelled?: () => boolean) => {
    try {
      const h = await paymentApi.getHistory();
      if (cancelled?.()) return;
      setDeposits(h.deposits);
      setDeductions(h.deductions);
    } catch {
      // History is auxiliary; keep the payment page usable when it fails.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    window.setTimeout(() => {
      void loadHistory(() => cancelled);
    }, 0);
    return () => {
      cancelled = true;
    };
  }, [loadHistory]);

  const handleDepositClose = useCallback((deposited?: boolean) => {
    setShowDeposit(false);
    if (deposited) {
      void refreshBalance();
      void loadHistory();
    }
  }, [refreshBalance, loadHistory]);

  const handleClaim = useCallback(async () => {
    const success = await claimDailyCredits();
    if (success) {
      void loadHistory();
    }
  }, [claimDailyCredits, loadHistory]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">积分</h1>
      </div>

      <Card>
        <Card.Content className="relative flex items-center justify-between gap-4 p-6">
          <button
            type="button"
            onClick={handleClaim}
            disabled={claimedToday || claiming}
            className={`absolute left-6 top-3 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              claimedToday
                ? 'cursor-not-allowed bg-default-100 text-default-400'
                : claiming
                  ? 'cursor-wait bg-green-500/10 text-green-600'
                  : 'cursor-pointer bg-green-500/10 text-green-600 hover:bg-green-500/20 active:bg-green-500/30'
            }`}
          >
            {claiming ? (
              <>
                <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                领取中...
              </>
            ) : claimedToday ? (
              '今日已领取'
            ) : (
              '领取积分'
            )}
          </button>
          <div className="text-center">
            <p className="text-sm text-default-500">当前余额</p>
            <p className="text-3xl font-bold text-amber-400">{balance >= 0 ? balance : 0}</p>
            <p className="mt-1 text-xs text-default-500">
              累计充值 {lifetimeCredits} 积分
            </p>
          </div>
          {claimError ? (
            <p className="absolute bottom-3 left-6 text-xs text-danger">{claimError}</p>
          ) : null}
          <button
            type="button"
            onClick={() => setShowDeposit(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-amber-500/25 transition-all"
          >
            <Coins className="h-4 w-4" />
            充值
          </button>
        </Card.Content>
      </Card>

      <Card>
        <Card.Content>
          <Card.Title className="mb-3 text-sm font-semibold text-foreground">收费标准</Card.Title>
          <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-default-100 p-3">
              <p className="text-default-500">充值汇率</p>
              <p className="font-medium text-foreground">1 USDT = {creditsPerDollar} 积分</p>
            </div>
            <div className="rounded-lg bg-default-100 p-3">
              <p className="text-default-500">Token 单价</p>
              <p className="font-medium text-foreground">1000 Token = {creditsPer1kTokens} 积分</p>
            </div>
          </div>
          <p className="mt-3 text-xs text-default-500">
            约 1 USDT = {Math.floor((creditsPerDollar / creditsPer1kTokens) * 1000).toLocaleString()} Token 使用量
          </p>
        </Card.Content>
      </Card>

      <Card>
        <Card.Header className="pb-0">
          <Card.Title className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <History className="h-4 w-4" />
            交易记录
          </Card.Title>
        </Card.Header>
        <Card.Content className="p-6 pt-4">
          {deposits.length === 0 && deductions.length === 0 ? (
            <EmptyState
              icon={<History className="h-10 w-10 text-default-400" />}
              title="暂无记录"
              description="充值或使用后将在此显示。"
            />
          ) : (
            <div className="space-y-4">
              {deposits.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-default-500">充值记录</p>
                  <div className="space-y-2">
                    {deposits.slice(0, 10).map((d) => (
                      <div key={d.id} className="flex items-center justify-between rounded-lg bg-default-100 px-3 py-2 text-sm">
                        <div>
                          <span className="font-medium text-emerald-400">+{d.creditAmount}</span>
                          <span className="ml-2 text-default-500">积分</span>
                          {d.reason ? (
                            <span className="ml-2 text-xs text-default-500">({d.reason})</span>
                          ) : null}
                        </div>
                        <div className="text-xs text-default-500">
                          {new Date(d.createdAt).toLocaleDateString('zh-CN')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {deductions.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-default-500">消费记录</p>
                  <div className="space-y-2">
                    {deductions.slice(0, 10).map((d) => (
                      <div key={d.id} className="flex items-center justify-between rounded-lg bg-default-100 px-3 py-2 text-sm">
                        <div>
                          <span className="font-medium text-red-400">-{d.creditsSpent}</span>
                          <span className="ml-2 text-default-500">
                            {d.callType === 'analysis' ? '分析' : d.callType === 'agent' ? '问股' : d.callType}
                          </span>
                        </div>
                        <div className="text-xs text-default-500">
                          {(d.totalTokens ?? 0).toLocaleString()} tokens
                          {' / '}
                          {new Date(d.createdAt).toLocaleDateString('zh-CN')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card.Content>
      </Card>

      <DepositDialog
        isOpen={showDeposit}
        onClose={handleDepositClose}
        creditsPerDollar={creditsPerDollar}
        creditsPer1kTokens={creditsPer1kTokens}
      />
    </div>
  );
};

export default PaymentPage;
