import { describe, expect, it } from 'vitest'

import i18n from '../../i18n'
import { SaleList } from '../SaleList'
import { makeSale } from '../../test/msw/handlers'
import { render, screen } from '../../test/test-utils'

function noop() {}

describe('SaleList', () => {
  it('uses logical text-start/text-end alignment on headers, never hardcoded text-left/text-right', () => {
    render(<SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />)

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
    const { container } = render(
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
    const { container } = render(
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

  it('wraps the table in a horizontally scrollable container for small screens', () => {
    const { container } = render(
      <SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />,
    )

    expect(container.querySelector('.overflow-x-auto table')).not.toBeNull()
  })

  it('places the customer name and contact directly under the Customer header in RTL', () => {
    expect(document.documentElement.dir).toBe('rtl')
    const { container } = render(
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
    render(
      <SaleList
        sales={[makeSale({ source: 'webhook', payment_method: 'card', source_provider: 'demo-pay' })]}
        onEdit={noop}
        onDelete={noop}
        onViewDocument={noop}
      />,
    )

    expect(screen.getByText('ספק תשלומים')).toBeInTheDocument()
  })

  it('keeps the same logical alignment classes after switching to English/LTR', async () => {
    await i18n.changeLanguage('en')
    expect(document.documentElement.dir).toBe('ltr')

    render(<SaleList sales={[makeSale()]} onEdit={noop} onDelete={noop} onViewDocument={noop} />)

    const headers = screen.getAllByRole('columnheader')
    expect(headers[0].className).toContain('text-start')
    expect(headers[4].className).toContain('text-end')
  })
})
