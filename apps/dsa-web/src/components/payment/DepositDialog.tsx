import React, { useEffect, useMemo, useState } from 'react';
import { Check, CreditCard, Landmark, Loader2, Wallet } from 'lucide-react';
import { Button, Input, Modal } from '@heroui/react';
import type { Connector } from 'wagmi';
import {
  useAccount,
  useConnect,
  useConnectors,
  useReadContract,
  useSwitchChain,
  useWaitForTransactionReceipt,
  useWriteContract,
} from 'wagmi';
import { sepolia } from 'wagmi/chains';
import { erc20Abi, isAddress, parseUnits } from 'viem';
import octIcon from '../../assets/oct.png';
import { paymentApi, type DepositConfigResponse } from '../../api/payment';

type DepositDialogProps = {
  isOpen: boolean;
  onClose: (deposited?: boolean) => void;
  creditsPerDollar: number;
  creditsPer1kTokens: number;
};

type PaymentMethod = 'crypto' | 'wechat' | 'alipay';

const METHOD_OPTIONS: Array<{
  id: PaymentMethod;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  isDisabled?: boolean;
}> = [
  { id: 'crypto', title: '加密货币', icon: Wallet },
  { id: 'wechat', title: '微信支付', icon: CreditCard, isDisabled: true },
  { id: 'alipay', title: '支付宝', icon: Landmark, isDisabled: true },
];

function getConnectorIcon(connector: Connector): string | undefined {
  return (connector as Connector & { icon?: string }).icon;
}

function getMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return '操作失败';
}

export const DepositDialog: React.FC<DepositDialogProps> = ({
  isOpen,
  onClose,
  creditsPerDollar,
}) => {
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>('crypto');
  const [availableConnectors, setAvailableConnectors] = useState<Connector[]>([]);
  const [octAmount, setOctAmount] = useState('');
  const [submittedHash, setSubmittedHash] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [depositConfig, setDepositConfig] = useState<DepositConfigResponse | null>(null);
  const [depositConfigError, setDepositConfigError] = useState<string | null>(null);
  const [isLoadingDepositConfig, setIsLoadingDepositConfig] = useState(false);
  const [isSubmittingHash, setIsSubmittingHash] = useState(false);

  const connectors = useConnectors();
  const { address, chainId, isConnected } = useAccount();
  const { connect, isPending, variables, error, reset } = useConnect();
  const { switchChain, isPending: isSwitchingChain } = useSwitchChain();
  const {
    data: txHash,
    error: writeError,
    isPending: isWriting,
    reset: resetWrite,
    writeContract,
  } = useWriteContract();

  const tokenAddress = depositConfig?.tokenAddress && isAddress(depositConfig.tokenAddress)
    ? depositConfig.tokenAddress
    : undefined;
  const receiverAddress = depositConfig?.receiverAddress && isAddress(depositConfig.receiverAddress)
    ? depositConfig.receiverAddress
    : undefined;
  const hasDepositConfig = Boolean(tokenAddress && receiverAddress);

  const { data: tokenDecimals } = useReadContract({
    address: tokenAddress,
    abi: erc20Abi,
    functionName: 'decimals',
    chainId: sepolia.id,
    query: { enabled: Boolean(tokenAddress) },
  });

  const { isLoading: isConfirming } = useWaitForTransactionReceipt({
    hash: txHash,
    chainId: sepolia.id,
    query: { enabled: Boolean(txHash) },
  });

  const visibleConnectors = useMemo(() => {
    const namedConnectors = availableConnectors.filter((connector) => connector.id !== 'injected');
    return namedConnectors.length > 0 ? namedConnectors : availableConnectors;
  }, [availableConnectors]);

  useEffect(() => {
    let cancelled = false;

    async function detectAvailableConnectors() {
      const detected = await Promise.all(
        connectors.map(async (connector) => {
          try {
            const provider = await connector.getProvider();
            return provider ? connector : null;
          } catch {
            return null;
          }
        }),
      );

      if (!cancelled) {
        setAvailableConnectors(detected.filter((connector): connector is Connector => Boolean(connector)));
      }
    }

    void detectAvailableConnectors();
    return () => {
      cancelled = true;
    };
  }, [connectors]);

  useEffect(() => {
    if (!isOpen || selectedMethod !== 'crypto') return;

    let cancelled = false;
    setIsLoadingDepositConfig(true);
    setDepositConfigError(null);

    paymentApi.getDepositConfig()
      .then((config) => {
        if (!cancelled) {
          setDepositConfig(config);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setDepositConfig(null);
          setDepositConfigError(getMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingDepositConfig(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, selectedMethod]);

  useEffect(() => {
    if (!txHash || !address || submittedHash === txHash) return;

    let cancelled = false;
    setIsSubmittingHash(true);
    setSubmitError(null);

    paymentApi.deposit(txHash, address)
      .then(() => {
        if (cancelled) return;
        setSubmittedHash(txHash);
        onClose(true);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSubmitError(getMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsSubmittingHash(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [address, onClose, submittedHash, txHash]);

  useEffect(() => {
    if (isOpen) return;
    reset();
    resetWrite();
    setSelectedMethod('crypto');
    setOctAmount('');
    setSubmittedHash(null);
    setSubmitError(null);
    setDepositConfigError(null);
    setIsSubmittingHash(false);
  }, [isOpen, reset, resetWrite]);

  const handleOpenChange = (open: boolean) => {
    if (open) return;
    onClose(false);
  };

  const handleMethodSelect = (method: PaymentMethod) => {
    setSelectedMethod(method);
    reset();
    resetWrite();
    setSubmitError(null);
  };

  const octValue = Number(octAmount);
  const estimatedCredits =
    Number.isFinite(octValue) && octValue > 0 ? Math.floor((octValue / 1.5) * creditsPerDollar) : 0;
  const parsedAmount = Number.isFinite(octValue) && octValue > 0
    ? parseUnits(octAmount, tokenDecimals ?? 18)
    : 0n;
  const isWrongChain = isConnected && chainId !== sepolia.id;
  const actionDisabled =
    !hasDepositConfig || parsedAmount <= 0n || isWriting || isConfirming || isSubmittingHash || isSwitchingChain;

  const handleDeposit = () => {
    setSubmitError(null);
    if (!tokenAddress || !receiverAddress || parsedAmount <= 0n) return;
    if (isWrongChain) {
      switchChain({ chainId: sepolia.id });
      return;
    }
    writeContract({
      address: tokenAddress,
      abi: erc20Abi,
      functionName: 'transfer',
      args: [receiverAddress, parsedAmount],
      chainId: sepolia.id,
    });
  };

  const actionText = isWrongChain
    ? '切换 Sepolia'
    : isWriting
      ? '确认钱包'
      : isConfirming
        ? '等待确认'
        : isSubmittingHash
          ? '入账中'
          : '充值';

  return (
    <Modal.Root isOpen={isOpen} onOpenChange={handleOpenChange}>
      <Modal.Backdrop variant="blur">
        <Modal.Container size="lg" placement="center">
          <Modal.Dialog>
            <Modal.Header>
              <Modal.Heading>充值</Modal.Heading>
              <Modal.CloseTrigger />
            </Modal.Header>

            <Modal.Body>
              <div className="grid min-h-[320px] gap-6 md:grid-cols-[150px_1fr]">
                <div className="flex flex-col gap-3">
                  {METHOD_OPTIONS.map((method) => {
                    const Icon = method.icon;
                    return (
                      <Button
                        key={method.id}
                        fullWidth
                        className="h-10 justify-start px-4 text-sm"
                        variant={selectedMethod === method.id ? 'primary' : 'ghost'}
                        isDisabled={method.isDisabled}
                        onPress={() => handleMethodSelect(method.id)}
                      >
                        <Icon className="h-5 w-5" />
                        {method.title}
                      </Button>
                    );
                  })}
                </div>

                <div className="flex min-h-[280px] items-center justify-center">
                  {selectedMethod === 'crypto' ? (
                    isConnected ? (
                      <div className="w-full max-w-md space-y-5">
                        <div className="flex items-center gap-4">
                          <img src={octIcon} alt="O币" className="h-12 w-12 rounded-full" />
                          <div>
                            <div className="text-xl font-semibold text-foreground">O币</div>
                            <div className="mt-1 text-sm text-default-500">1 USDT = 1.5 O币</div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="text-sm text-default-500">充值数量</div>
                          <div className="relative">
                            <Input
                              type="number"
                              placeholder="输入O币数量"
                              value={octAmount}
                              min={0}
                              step="0.01"
                              className="pr-20"
                              fullWidth
                              onChange={(event) => setOctAmount(event.target.value)}
                            />
                            <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center gap-2 text-sm text-default-600">
                              <img src={octIcon} alt="" className="h-5 w-5 rounded-full" />
                              <span>O币</span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-1">
                          <div className="text-sm text-default-500">预计到账</div>
                          <div className="text-2xl font-semibold text-foreground">
                            {estimatedCredits.toLocaleString()} 积分
                          </div>
                        </div>

                        {!hasDepositConfig ? (
                          <div className="text-sm text-danger">
                            {depositConfigError ?? '未配置收款信息'}
                          </div>
                        ) : null}
                        {writeError ? <div className="text-sm text-danger">{writeError.message}</div> : null}
                        {submitError ? <div className="text-sm text-danger">{submitError}</div> : null}

                        <Button
                          fullWidth
                          className="h-12 text-base font-medium"
                          variant="primary"
                          isDisabled={actionDisabled || isLoadingDepositConfig}
                          onPress={handleDeposit}
                        >
                          {isLoadingDepositConfig || isWriting || isConfirming || isSubmittingHash || isSwitchingChain ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : null}
                          {isLoadingDepositConfig ? '加载中' : actionText}
                        </Button>
                      </div>
                    ) : (
                      <div className="w-full max-w-md space-y-3">
                        {visibleConnectors.length > 0 ? (
                          visibleConnectors.map((connector) => {
                            const icon = getConnectorIcon(connector);
                            const connecting = isPending && variables?.connector === connector;
                            return (
                              <Button
                                key={connector.uid}
                                fullWidth
                                className="h-12 justify-start px-4 text-sm"
                                variant="ghost"
                                isDisabled={isPending}
                                onPress={() => connect({ connector, chainId: sepolia.id })}
                              >
                                {icon ? (
                                  <img src={icon} alt="" className="h-5 w-5 rounded" />
                                ) : (
                                  <Wallet className="h-5 w-5" />
                                )}
                                {connector.name}
                                {connecting ? <Loader2 className="ml-auto h-4 w-4 animate-spin" /> : null}
                              </Button>
                            );
                          })
                        ) : (
                          <div className="text-sm text-default-500">未检测到钱包</div>
                        )}

                        {error ? <div className="text-sm text-danger">{error.message}</div> : null}
                      </div>
                    )
                  ) : (
                    <div className="flex items-center gap-3 text-sm text-default-500">
                      <Check className="h-5 w-5" />
                      待接入
                    </div>
                  )}
                </div>
              </div>
            </Modal.Body>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal.Root>
  );
};
