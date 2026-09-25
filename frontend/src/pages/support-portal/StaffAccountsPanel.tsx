import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from '../../components/FormField'
import { Modal } from '../../components/Modal'
import { ErrorState, LoadingState } from '../../components/StatusStates'
import { Card } from '../../components/ui'
import { buttonClasses, cx } from '../../components/ui-classes'
import {
  createStaffUser, deleteStaffUser, listStaffUsers, updateStaffUserRole,
  type ManagedRole, type StaffUser, type StaffUserCreate,
} from '../../services/adminService'

const emptyAccount: StaffUserCreate = { email: '', password: '', name: '', system_role: 'support' }

export function StaffAccountsPanel({ currentUserId }: { currentUserId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [account, setAccount] = useState<StaffUserCreate>(emptyAccount)
  const [userRemoval, setUserRemoval] = useState<StaffUser | null>(null)
  const [confirmEmail, setConfirmEmail] = useState('')
  const users = useQuery({ queryKey: ['staff-users'], queryFn: listStaffUsers })
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['staff-users'] })
  const removeUser = useMutation({ mutationFn: deleteStaffUser, onSuccess: () => { setUserRemoval(null); setConfirmEmail(''); refresh() } })
  const createUser = useMutation({ mutationFn: createStaffUser, onSuccess: () => { setAccount(emptyAccount); setShowCreate(false); refresh() } })
  const changeRole = useMutation({ mutationFn: ({ id, role }: { id: string; role: ManagedRole }) => updateStaffUserRole(id, role), onSuccess: refresh })

  function submitAccount(event: FormEvent) {
    event.preventDefault()
    createUser.mutate({ ...account, email: account.email.trim(), name: account.name.trim() })
  }

  return (
    <section aria-labelledby="users-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="users-heading" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.accounts.title')}</h2>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{t('supportPortal.accounts.description')}</p>
        </div>
        <button type="button" className={buttonClasses('primary')} onClick={() => setShowCreate(true)}>
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          {t('supportPortal.accounts.create')}
        </button>
      </div>

      {users.isPending && <LoadingState label={t('supportPortal.accounts.loading')} />}
      {users.isError && <ErrorState message={t('supportPortal.accounts.loadError')} onRetry={() => void users.refetch()} />}
      {users.data && (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {users.data.map((item) => {
              const initial = (item.name?.trim() || item.email).charAt(0).toLocaleUpperCase()
              return (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-zinc-100 text-sm font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300" aria-hidden="true">{initial}</span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50" dir="ltr">{item.email}</p>
                      <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                        {item.business_name || t('supportPortal.accounts.noBusiness')} · {t(`supportPortal.roles.${item.system_role}`)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.system_role !== 'superadmin' && (
                      <select
                        aria-label={t('supportPortal.accounts.roleFor', { email: item.email })}
                        className={cx(inputClasses, 'w-auto')}
                        value={item.system_role}
                        disabled={changeRole.isPending}
                        onChange={(event) => changeRole.mutate({ id: item.id, role: event.target.value as ManagedRole })}
                      >
                        <option value="user">{t('supportPortal.roles.user')}</option>
                        <option value="support">{t('supportPortal.roles.support')}</option>
                        <option value="admin">{t('supportPortal.roles.admin')}</option>
                      </select>
                    )}
                    {item.id !== currentUserId && item.system_role !== 'superadmin' && (
                      <button
                        type="button"
                        aria-label={t('supportPortal.accounts.deleteFor', { email: item.email })}
                        title={t('supportPortal.accounts.delete')}
                        className="grid h-10 w-10 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-danger-50 hover:text-danger-700 dark:text-zinc-400 dark:hover:bg-danger-500/10 dark:hover:text-danger-500"
                        onClick={() => { setUserRemoval(item); setConfirmEmail('') }}
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
      {changeRole.isError && <p role="alert" className="text-sm text-danger-700 dark:text-danger-500">{t('supportPortal.accounts.roleError')}</p>}

      {showCreate && (
        <Modal title={t('supportPortal.accounts.create')} onClose={() => { setShowCreate(false); createUser.reset() }}>
          <form className="space-y-4" onSubmit={submitAccount}>
            <FormField label={t('supportPortal.accounts.form.name')} htmlFor="new-account-name">
              <input id="new-account-name" className={inputClasses} value={account.name} onChange={(event) => setAccount({ ...account, name: event.target.value })} />
            </FormField>
            <FormField
              label={t('supportPortal.accounts.form.login')}
              htmlFor="new-account-email"
              hint={account.system_role === 'user' ? t('supportPortal.accounts.form.loginHintUser') : undefined}
            >
              <input id="new-account-email" dir="ltr" type="text" autoComplete="off" required className={inputClasses} value={account.email} onChange={(event) => setAccount({ ...account, email: event.target.value })} />
            </FormField>
            <FormField label={t('supportPortal.accounts.form.password')} htmlFor="new-account-password">
              <input id="new-account-password" dir="ltr" type="password" autoComplete="new-password" required minLength={12} className={inputClasses} value={account.password} onChange={(event) => setAccount({ ...account, password: event.target.value })} />
            </FormField>
            <FormField label={t('supportPortal.accounts.form.role')} htmlFor="new-account-role">
              <select id="new-account-role" className={inputClasses} value={account.system_role} onChange={(event) => setAccount({ ...account, system_role: event.target.value as ManagedRole })}>
                <option value="support">{t('supportPortal.roles.support')}</option>
                <option value="admin">{t('supportPortal.roles.admin')}</option>
                <option value="user">{t('supportPortal.roles.user')}</option>
              </select>
            </FormField>
            {createUser.isError && <p role="alert" className="text-sm text-danger-700 dark:text-danger-500">{createUser.error.message}</p>}
            <div className="flex flex-col-reverse gap-2 border-t border-zinc-100 pt-4 sm:flex-row sm:justify-end dark:border-zinc-800">
              <button type="button" className={buttonClasses('secondary')} onClick={() => setShowCreate(false)}>{t('supportPortal.accounts.form.cancel')}</button>
              <button type="submit" className={buttonClasses('primary')} disabled={createUser.isPending}>
                {createUser.isPending ? t('supportPortal.accounts.form.submitting') : t('supportPortal.accounts.form.submit')}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {userRemoval && (
        <Modal title={t('supportPortal.accounts.deleteTitle', { email: userRemoval.email })} onClose={() => setUserRemoval(null)}>
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t('supportPortal.accounts.deleteDescription')}</p>
          <div className="mt-4">
            <FormField label={t('supportPortal.accounts.deleteConfirmLabel')} htmlFor="confirm-delete-user">
              <input id="confirm-delete-user" dir="ltr" className={inputClasses} value={confirmEmail} onChange={(event) => setConfirmEmail(event.target.value)} />
            </FormField>
          </div>
          {removeUser.isError && <p role="alert" className="mt-3 text-sm text-danger-700 dark:text-danger-500">{removeUser.error.message}</p>}
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" className={buttonClasses('secondary')} onClick={() => setUserRemoval(null)}>{t('supportPortal.accounts.form.cancel')}</button>
            <button
              type="button"
              className={buttonClasses('danger')}
              disabled={confirmEmail !== userRemoval.email || removeUser.isPending}
              onClick={() => removeUser.mutate(userRemoval.id)}
            >
              {removeUser.isPending ? t('supportPortal.accounts.deleting') : t('supportPortal.accounts.delete')}
            </button>
          </div>
        </Modal>
      )}
    </section>
  )
}
