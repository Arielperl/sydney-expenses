import { apiClient, toApiError } from './apiClient'
import type { Expense } from '../types/expense'
import type {
  EligibleExpense,
  MatchDecisionResponse,
  ReconciliationInbox,
  RematchResponse,
} from '../types/reconciliation'

export async function getReconciliationInbox(): Promise<ReconciliationInbox> {
  try {
    const response = await apiClient.get<ReconciliationInbox>('/reconciliation/inbox')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function approveMatch(expenseId: string): Promise<Expense> {
  try {
    const response = await apiClient.post<MatchDecisionResponse>(`/reconciliation/matches/${expenseId}/approve`)
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

export async function attachMatch(uploadId: string, expenseId: string): Promise<Expense> {
  try {
    const response = await apiClient.post<MatchDecisionResponse>('/reconciliation/attach', {
      upload_id: uploadId,
      expense_id: expenseId,
    })
    return response.data.expense
  } catch (error) {
    throw toApiError(error)
  }
}

export async function rematchDocument(uploadId: string): Promise<RematchResponse> {
  try {
    const response = await apiClient.post<RematchResponse>(`/reconciliation/documents/${uploadId}/rematch`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function listEligibleExpenses(uploadId: string): Promise<EligibleExpense[]> {
  try {
    const response = await apiClient.get<EligibleExpense[]>(`/reconciliation/documents/${uploadId}/eligible-expenses`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function discardDocument(uploadId: string): Promise<void> {
  try {
    await apiClient.post(`/reconciliation/documents/${uploadId}/discard`)
  } catch (error) {
    throw toApiError(error)
  }
}
