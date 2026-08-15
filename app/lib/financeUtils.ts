import type { Account, AccountBalance } from "./api";

export const fmt = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

export const fmtFull = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export function accountTypeOrder(type: string): number {
  return { checking: 0, savings: 1, brokerage: 2, investment: 3, crypto: 4, credit: 5 }[type] ?? 9;
}

export function groupBalancesByType(
  balances: AccountBalance[],
  accounts: Account[]
): Record<string, AccountBalance[]> {
  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a]));
  const groups: Record<string, AccountBalance[]> = {};
  for (const b of balances) {
    const type = accountMap[b.account_id]?.type ?? b.account_type;
    if (!groups[type]) groups[type] = [];
    groups[type].push(b);
  }
  return groups;
}
