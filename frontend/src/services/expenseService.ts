import { apiClient, toApiError } from './apiClient'
import type { Expense, ExpenseFilters, ExpenseInput } from '../types/expense'

export async function listExpenses(filters: ExpenseFilters = {}): Promise<Expense[]> {
  try {
    const params: Record<string, string> = {}
    if (filters.search) params.search = filters.search
    if (filters.category) params.category = filters.category
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to

    const response = await apiClient.get<Expense[]>('/expenses', { params })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function getExpense(id: string): Promise<Expense> {
  try {
    const response = await apiClient.get<Expense>(`/expenses/${id}`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function createExpense(input: ExpenseInput): Promise<Expense> {
  try {
    const response = await apiClient.post<Expense>('/expenses', input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function updateExpense(id: string, input: Partial<ExpenseInput>): Promise<Expense> {
  try {
    const response = await apiClient.put<Expense>(`/expenses/${id}`, input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function deleteExpense(id: string): Promise<void> {
  try {
    await apiClient.delete(`/expenses/${id}`)
  } catch (error) {
    throw toApiError(error)
  }
}
