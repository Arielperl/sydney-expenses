import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { ExpenseForm } from '../components/ExpenseForm'
import { ManualMatchDialog } from '../components/ManualMatchDialog'
import { MatchSuggestionCard } from '../components/MatchSuggestionCard'
import { Modal } from '../components/Modal'
import { ErrorState, LoadingState } from '../components/StatusStates'
import { UnassignedDocumentCard } from '../components/UnassignedDocumentCard'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { confirmReceipt } from '../services/receiptService'
import {
  approveMatch,
  attachMatch,
  discardDocument,
  getReconciliationInbox,
  rejectMatch,
  rematchDocument,
} from '../services/reconciliationService'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import type { Expense } from '../types/expense'
import type { UnassignedDocument } from '../types/reconciliation'

function documentToFormValues(document: UnassignedDocument): Partial<ExpenseFormInput> {
  return {
    business_name: document.extracted_business_name ?? '',
    receipt_number: document.extracted_receipt_number ?? '',
    amount: document.extracted_total ?? '',
    vat_amount: document.extracted_vat ?? '',
    currency: document.extracted_currency || 'ILS',
    category: document.extracted_category ?? 'other',
    expense_date: document.extracted_date ?? '',
  }
}

function TransactionRow({ expense }: { expense: Expense }) {
  const { t, i18n } = useTranslation()
  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
        <p className="text-xs text-stone-500 dark:text-stone-400">{formatDate(expense.expense_date, i18n.language)}</p>
      </div>
      <div className="flex items-center gap-3">
        <DocumentStatusBadge status={expense.document_status} />
        <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
          {formatCurrency(expense.amount, expense.currency, i18n.language)}
        </span>
        {expense.document_status === 'missing' && (
          <Link
            to={`/upload-receipt?expenseId=${expense.id}`}
            className="whitespace-nowrap rounded-md border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
          >
            {t('reconciliation.attachReceipt')}
          </Link>
        )}
      </div>
    </li>
  )
}

function ExpenseListSection({
  title,
  emptyLabel,
  expenses,
}: {
  title: string
  emptyLabel: string
  expenses: Expense[]
}) {
  return (
    <section>
      <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{title}</h2>
      {expenses.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">{emptyLabel}</p>
      ) : (
        <ul className="mt-3 divide-y divide-stone-100 rounded-2xl border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {expenses.map((expense) => (
            <TransactionRow key={expense.id} expense={expense} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function ReconciliationInboxPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [manualMatchDocument, setManualMatchDocument] = useState<UnassignedDocument | null>(null)
  const [createExpenseDocument, setCreateExpenseDocument] = useState<UnassignedDocument | null>(null)
  const [discardingDocument, setDiscardingDocument] = useState<UnassignedDocument | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reconciliation-inbox'],
    queryFn: getReconciliationInbox,
  })

  function invalidateInboxRelated() {
    queryClient.invalidateQueries({ queryKey: ['reconciliation-inbox'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    queryClient.invalidateQueries({ queryKey: ['expenses'] })
  }

  const approveMutation = useMutation({
    mutationFn: (expenseId: string) => approveMatch(expenseId),
    onSuccess: invalidateInboxRelated,
  })
  const rejectMutation = useMutation({
    mutationFn: (expenseId: string) => rejectMatch(expenseId),
    onSuccess: invalidateInboxRelated,
  })

  const rematchMutation = useMutation({
    mutationFn: (uploadId: string) => rematchDocument(uploadId),
    onSuccess: invalidateInboxRelated,
  })

  const attachMutation = useMutation({
    mutationFn: ({ uploadId, expenseId }: { uploadId: string; expenseId: string }) => attachMatch(uploadId, expenseId),
    onSuccess: () => {
      invalidateInboxRelated()
      setManualMatchDocument(null)
    },
  })

  const discardMutation = useMutation({
    mutationFn: (uploadId: string) => discardDocument(uploadId),
    onSuccess: () => {
      invalidateInboxRelated()
      setDiscardingDocument(null)
    },
  })

  const createExpenseMutation = useMutation({
    mutationFn: (values: ExpenseFormValues) => {
      if (!createExpenseDocument) throw new Error('No document selected')
      return confirmReceipt({
        upload_id: createExpenseDocument.id,
        business_name: values.business_name,
        receipt_number: values.receipt_number || null,
        amount: Number(values.amount),
        vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
        currency: values.currency,
        category: values.category,
        expense_date: values.expense_date,
        payment_method: values.payment_method || null,
        notes: values.notes || null,
        extraction_confidence: createExpenseDocument.extraction_confidence,
      })
    },
    onSuccess: () => {
      invalidateInboxRelated()
      setCreateExpenseDocument(null)
    },
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />
  if (isError) return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('reconciliation.title')}</h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('reconciliation.subtitle')}</p>
        </div>
        <Link
          to="/upload-receipt"
          className="shrink-0 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
        >
          {t('reconciliation.uploadUnassignedDocument')}
        </Link>
      </div>

      <section>
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
          {t('reconciliation.sections.suggestedMatches')}
        </h2>
        {data.suggested_matches.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">{t('reconciliation.emptySuggestedMatches')}</p>
        ) : (
          <div className="mt-3 space-y-3">
            {data.suggested_matches.map((match) => (
              <MatchSuggestionCard
                key={match.expense.id}
                expense={match.expense}
                document={match.document}
                onApprove={() => approveMutation.mutate(match.expense.id)}
                onReject={() => rejectMutation.mutate(match.expense.id)}
                isApproving={approveMutation.isPending && approveMutation.variables === match.expense.id}
                isRejecting={rejectMutation.isPending && rejectMutation.variables === match.expense.id}
              />
            ))}
          </div>
        )}
      </section>

      <ExpenseListSection
        title={t('reconciliation.sections.missingDocuments')}
        emptyLabel={t('reconciliation.emptyMissingDocuments')}
        expenses={data.missing_documents}
      />

      <section>
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
          {t('reconciliation.sections.documentsWithoutTransactions')}
        </h2>
        {data.documents_without_transactions.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">
            {t('reconciliation.emptyDocumentsWithoutTransactions')}
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {data.documents_without_transactions.map((document) => (
              <UnassignedDocumentCard
                key={document.id}
                document={document}
                onRematch={() => rematchMutation.mutate(document.id)}
                onChooseTransaction={() => setManualMatchDocument(document)}
                onCreateExpense={() => setCreateExpenseDocument(document)}
                onDiscard={() => setDiscardingDocument(document)}
                isRematching={rematchMutation.isPending && rematchMutation.variables === document.id}
              />
            ))}
          </div>
        )}
      </section>

      <ExpenseListSection
        title={t('reconciliation.sections.recentlyCompleted')}
        emptyLabel={t('reconciliation.emptyRecentlyCompleted')}
        expenses={data.recently_completed}
      />

      {manualMatchDocument && (
        <ManualMatchDialog
          document={manualMatchDocument}
          onClose={() => setManualMatchDocument(null)}
          onConfirm={(expenseId) => attachMutation.mutate({ uploadId: manualMatchDocument.id, expenseId })}
          isConfirming={attachMutation.isPending}
          confirmingExpenseId={attachMutation.variables?.expenseId ?? null}
        />
      )}

      {createExpenseDocument && (
        <Modal title={t('reconciliation.document.createExpense')} onClose={() => setCreateExpenseDocument(null)}>
          <ExpenseForm
            defaultValues={documentToFormValues(createExpenseDocument)}
            submitLabel={t('form.saveExpense')}
            isSubmitting={createExpenseMutation.isPending}
            submitError={createExpenseMutation.isError ? toApiError(createExpenseMutation.error).message : null}
            onSubmit={(values) => createExpenseMutation.mutate(values)}
          />
        </Modal>
      )}

      {discardingDocument && (
        <Modal title={t('reconciliation.document.discardConfirmTitle')} onClose={() => setDiscardingDocument(null)}>
          <p className="text-sm text-stone-600 dark:text-stone-400">{t('reconciliation.document.discardConfirmBody')}</p>
          {discardMutation.isError && (
            <p role="alert" className="mt-2 text-sm text-danger-600">
              {toApiError(discardMutation.error).message}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDiscardingDocument(null)}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={discardMutation.isPending}
              onClick={() => discardMutation.mutate(discardingDocument.id)}
              className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
            >
              {discardMutation.isPending ? t('common.deleting') : t('common.delete')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
