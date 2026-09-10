import { apiClient, toApiError } from './apiClient'
import type { Expense } from '../types/expense'
import type { ApproveMatchInput, MatchDecisionResponse, ReconciliationInbox } from '../types/reconciliation'

export async function getReconciliationInbox(): Promise<ReconciliationInbox> {
  try {
    const response = await apiClient.get<ReconciliationInbox>('/reconciliation/inbox')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function approveMatch(expenseId: string, input: ApproveMatchInput = {}): Promise<Expense> {
  try {
    const response = await apiClient.post<MatchDecisionResponse>(
      `/reconciliation/matches/${expenseId}/approve`,
      input,
    )
    return response.data.expense
  } catch (error) {
    throw toApiError(error)
  }
}

export async function rejectMatch(expenseId: string): Promise<Expense> {
  try {
    const response = await apiClient.post<MatchDecisionResponse>(`/reconciliation/matches/${expenseId}/reject`)
    return response.data.expense
  } catch (error) {
    throw toApiError(error)
  }
}
