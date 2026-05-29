import { create } from 'zustand';
import { paymentApi } from '../api/payment';

interface CreditState {
  balance: number;
  lifetimeCredits: number;
  creditsPerDollar: number;
  creditsPer1kTokens: number;
  claimedToday: boolean;
  claiming: boolean;
  claimError: string | null;
  loading: boolean;
  error: string | null;
}

interface CreditActions {
  initialize: () => Promise<void>;
  refreshBalance: () => Promise<void>;
  claimDailyCredits: () => Promise<boolean>;
  reset: () => void;
}

export const useCreditStore = create<CreditState & CreditActions>((set) => ({
  balance: 0,
  lifetimeCredits: 0,
  creditsPerDollar: 100,
  creditsPer1kTokens: 10,
  claimedToday: false,
  claiming: false,
  claimError: null,
  loading: false,
  error: null,

  initialize: async () => {
    set({ loading: true, error: null });
    try {
      const [balance, rate] = await Promise.all([
        paymentApi.getBalance(),
        paymentApi.getRate().catch(() => ({ creditsPerDollar: 100, creditsPer1kTokens: 10 })),
      ]);
      set({
        balance: balance.balance,
        lifetimeCredits: balance.lifetimeCredits,
        claimedToday: balance.claimedToday ?? false,
        creditsPerDollar: rate.creditsPerDollar,
        creditsPer1kTokens: rate.creditsPer1kTokens,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load payment info';
      set({ error: message });
    } finally {
      set({ loading: false });
    }
  },

  refreshBalance: async () => {
    try {
      const data = await paymentApi.getBalance();
      set({
        balance: data.balance,
        lifetimeCredits: data.lifetimeCredits,
        claimedToday: data.claimedToday ?? false,
      });
    } catch {
      // silent
    }
  },

  claimDailyCredits: async () => {
    set({ claiming: true, claimError: null });
    try {
      const result = await paymentApi.claimCredits();
      set({
        balance: result.balance,
        claimedToday: true,
        claiming: false,
      });
      return true;
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: { message?: string } } } };
      if (axiosErr.response?.status === 409) {
        set({ claimedToday: true, claiming: false });
        return false;
      }
      const message = axiosErr.response?.data?.detail?.message ?? '领取失败，请稍后重试';
      set({ claimError: message, claiming: false });
      return false;
    }
  },

  reset: () => {
    set({
      balance: 0,
      lifetimeCredits: 0,
      creditsPerDollar: 100,
      creditsPer1kTokens: 10,
      claimedToday: false,
      claiming: false,
      claimError: null,
      loading: false,
      error: null,
    });
  },
}));
