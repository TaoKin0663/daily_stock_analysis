import React, { useEffect } from 'react';
import { Coins } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCreditStore } from '../../stores/creditStore';

export const CreditBalanceBadge: React.FC = () => {
  const { balance, initialize } = useCreditStore();

  useEffect(() => {
    void initialize();
  }, [initialize]);

  return (
    <Link
      to="/payment"
      className="flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs text-amber-400 transition-colors hover:bg-amber-500/20"
      title="积分余额"
    >
      <Coins className="h-3.5 w-3.5" />
      <span>{balance >= 0 ? balance : 0}</span>
    </Link>
  );
};
