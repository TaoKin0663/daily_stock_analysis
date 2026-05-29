import apiClient from './index';
import { toCamelCase } from './utils';

export type BalanceResponse = {
  balance: number;
  lifetimeCredits: number;
  claimedToday?: boolean;
};

export type RateResponse = {
  creditsPerDollar: number;
  creditsPer1kTokens: number;
};

export type ClaimResponse = {
  balance: number;
  claimed: boolean;
};

export type DepositConfigResponse = {
  chainId: number;
  receiverAddress: string;
  tokenAddress: string;
};

export type DepositResponse = {
  success: boolean;
  depositId: number;
  transactionId?: number | null;
  creditAmount: number;
  balance: number;
  status: 'pending' | 'succeeded';
};

export type DepositHistoryItem = {
  id: number;
  creditAmount: number;
  operatorUserId?: number | null;
  reason?: string | null;
  createdAt: string;
};

export type DeductionHistoryItem = {
  id: number;
  callType: string;
  model: string;
  totalTokens: number;
  creditsSpent: number;
  balanceAfter: number;
  createdAt: string;
};

export type HistoryResponse = {
  deposits: DepositHistoryItem[];
  deductions: DeductionHistoryItem[];
};

export const paymentApi = {
  async getBalance(): Promise<BalanceResponse> {
    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/payment/balance');
    return toCamelCase<BalanceResponse>(data);
  },

  async getRate(): Promise<RateResponse> {
    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/payment/rate');
    return toCamelCase<RateResponse>(data);
  },

  async getDepositConfig(): Promise<DepositConfigResponse> {
    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/payment/deposit/config');
    return toCamelCase<DepositConfigResponse>(data);
  },

  async deposit(txHash: string, walletAddress: string): Promise<DepositResponse> {
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/payment/deposit', {
      tx_hash: txHash,
      wallet_address: walletAddress,
    });
    return toCamelCase<DepositResponse>(data);
  },

  async getHistory(): Promise<HistoryResponse> {
    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/payment/history');
    return toCamelCase<HistoryResponse>(data);
  },

  async claimCredits(): Promise<ClaimResponse> {
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/payment/claim');
    return toCamelCase<ClaimResponse>(data);
  },
};
