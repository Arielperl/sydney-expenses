import { describe, expect, it } from 'vitest'

import i18n from '../../i18n'
import { SaleList } from '../SaleList'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen } from '../../test/test-utils'

function noop() {}

describe('SaleList', () => {
  it('uses logical text-start/text-end alignment on headers, never hardcoded text-left/text-right', () => {
    renderWithProviders(<SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />)

    const headers = screen.getAllByRole('columnheader')
    expect(headers).toHaveLength(6)

    // Customer, Service, Status, Date are logically start-aligned.
    for (const header of headers.slice(0, 4)) {
      expect(header.className).toContain('text-start')
      expect(header.className).not.toContain('text-left')
      expect(header.className).not.toContain('text-right')
    }
    // Amount and Actions are logically end-aligned.
    for (const header of headers.slice(4)) {
      expect(header.className).toContain('text-end')
      expect(header.className).not.toContain('text-left')
      expect(header.className).not.toContain('text-right')
    }
  })

  it('mirrors the same logical alignment on the body cells as the headers', () => {
    const { container } = renderWithProviders(
      <SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />,
    )

    const row = container.querySelector('tbody tr')!
    const cells = Array.from(row.querySelectorAll('td'))
    expect(cells).toHaveLength(6)

    for (const cell of cells.slice(0, 4)) {
      expect(cell.className).toContain('text-start')
    }
    for (const cell of cells.slice(4)) {
      expect(cell.className).toContain('text-end')
    }
    for (const cell of cells) {
      expect(cell.className).not.toContain('text-left')
      expect(cell.className).not.toContain('text-right')
    }
  })

  it('gives every column a stable, fixed width via a colgroup so the actions column never shifts the data columns', () => {
    const { container } = renderWithProviders(
      <SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />,
    )

    const table = container.querySelector('table')!
    expect(table.className).toContain('table-fixed')
    const cols = container.querySelectorAll('colgroup col')
    expect(cols).toHaveLength(6)
    for (const col of cols) {
      expect(col.className).toMatch(/w-\[\d+%\]/)
    }
  })

  it('stacks rows as cards on phones and keeps the table scrollable from tablet width up', () => {
    const { container } = renderWithProviders(
      <SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />,
    )

    // Tablet/desktop: the real table sits in a horizontally scrollable container.
    expect(container.querySelector('.md\\:overflow-x-auto table')).not.toBeNull()
    // Phone: each row becomes a self-contained card instead of forcing sideways scrolling.
    expect(container.querySelector('tbody tr')!.className).toContain('max-md:grid')
    expect(container.querySelector('thead')!.className).toContain('max-md:hidden')
  })

  it('places the customer name and contact directly under the Customer header in RTL', () => {
    expect(document.documentElement.dir).toBe('rtl')
    const { container } = renderWithProviders(
      <SaleList sales={[makeSale({ customer_contact: 'dana@example.com' })]} onEdit={noop} onDelete={noop} onViewDocument={noop} />,
    )

    const headerCells = screen.getAllByRole('columnheader')
    const customerHeader = headerCells[0]
    const row = container.querySelector('tbody tr')!
    const customerCell = row.querySelectorAll('td')[0]

    expect(customerCell.className).toContain('text-start')
    expect(customerHeader.className).toContain('text-start')
    expect(customerCell.textContent).toContain('Dana Cohen')
    expect(customerCell.textContent).toContain('dana@example.com')
  })

  it('renders a webhook-created sale (payment provider source) without crashing', () => {
    renderWithProviders(
      <SaleList
        sales={[makeSale({ source: 'webhook', payment_method: 'card', source_provider: 'demo-pay' })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.getByText('ספק תשלומים')).toBeInTheDocument()
  })

  it('shows the VAT amount and tax treatment under the sale amount', () => {
    renderWithProviders(
      <SaleList
        sales={[makeSale({ vat_amount: '18.00', tax_treatment: 'standard' })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.getByText(/18\.00/)).toBeInTheDocument()
    expect(screen.getByText('מע"מ רגיל — 18%')).toBeInTheDocument()
  })

  it('shows a "needs review" note instead of a fabricated VAT for a legacy sale with no tax treatment', () => {
    renderWithProviders(
      <SaleList
        sales={[makeSale({ tax_treatment: null, tax_treatment_needs_review: true })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.getByText('סוג העסקה (מע"מ) דורש בדיקה')).toBeInTheDocument()
  })

  it('notes that a foreign-currency sale still uses the Israeli demo tax profile', () => {
    renderWithProviders(
      <SaleList
        sales={[makeSale({ currency: 'USD', tax_treatment: 'standard' })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.getByText('עדיין ממוסה לפי כללי מע"מ ישראלי')).toBeInTheDocument()
  })

  it('does not show the Israeli-tax note for an ILS sale', () => {
    renderWithProviders(
      <SaleList
        sales={[makeSale({ currency: 'ILS' })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.queryByText('עדיין ממוסה לפי כללי מע"מ ישראלי')).not.toBeInTheDocument()
  })

  it('links the customer name to that sale\'s details page', () => {
    const sale = makeSale()
    renderWithProviders(<SaleList sales={[sale]} onEdit={noop} onDelete={noop} onViewDocument={noop} />)

    expect(screen.getByRole('link', { name: sale.customer_name })).toHaveAttribute('href', `/sales/${sale.id}`)
  })

  it('keeps the same logical alignment classes after switching to English/LTR', async () => {
    await i18n.changeLanguage('en')
    expect(document.documentElement.dir).toBe('ltr')

    renderWithProviders(<SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />)

    const headers = screen.getAllByRole('columnheader')
    expect(headers[0].className).toContain('text-start')
    expect(headers[4].className).toContain('text-end')
  })
})
