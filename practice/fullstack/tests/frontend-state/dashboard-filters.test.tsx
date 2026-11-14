// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { memo } from 'react';
import {
  FiltersProvider,
  filtersReducer,
  initialFilters,
  useFilters,
  useFiltersDispatch,
  type Filters,
} from '../../exercises/frontend-state/dashboardFilters.js';

const frozen = (filters: Filters): Filters => Object.freeze({ ...filters });

describe('filtersReducer', { tags: ['@exercise'] }, () => {
  it('changes the status without mutating the previous state, and goes back to page 1', () => {
    const before = frozen({ status: 'ALL', search: '', page: 3 });
    const after = filtersReducer(before, { type: 'status-changed', status: 'PAID' });
    expect(after).toEqual({ status: 'PAID', search: '', page: 1 });
    expect(before).toEqual({ status: 'ALL', search: '', page: 3 });
  });

  it('trims the search text and goes back to page 1', () => {
    const after = filtersReducer(frozen({ status: 'PAID', search: '', page: 4 }), {
      type: 'search-changed',
      search: '  ord_10 ',
    });
    expect(after).toEqual({ status: 'PAID', search: 'ord_10', page: 1 });
  });

  it('returns the same state object when nothing changes, so React can skip the render', () => {
    const state = frozen({ status: 'PAID', search: 'ord_10', page: 2 });
    expect(filtersReducer(state, { type: 'status-changed', status: 'PAID' })).toBe(state);
    expect(filtersReducer(state, { type: 'search-changed', search: 'ord_10 ' })).toBe(state);
    expect(filtersReducer(state, { type: 'page-changed', page: 2 })).toBe(state);
  });

  it('ignores impossible pages', () => {
    const state = frozen({ status: 'ALL', search: '', page: 2 });
    expect(filtersReducer(state, { type: 'page-changed', page: 0 })).toBe(state);
    expect(filtersReducer(state, { type: 'page-changed', page: -1 })).toBe(state);
    expect(filtersReducer(state, { type: 'page-changed', page: 1.5 })).toBe(state);
    expect(filtersReducer(state, { type: 'page-changed', page: 5 })).toEqual({ ...state, page: 5 });
  });

  it('resets to the initial filters', () => {
    const state = frozen({ status: 'FAILED', search: 'ord', page: 7 });
    expect(filtersReducer(state, { type: 'reset' })).toEqual(initialFilters);
  });
});

describe('FiltersProvider and its hooks', { tags: ['@exercise'] }, () => {
  function Summary() {
    const { status, page } = useFilters();
    return (
      <p>
        Showing {status} orders, page {page}
      </p>
    );
  }

  let toolbarRenders = 0;
  // memo: the toolbar gets no props, so only a context it reads can re-render it.
  const Toolbar = memo(function Toolbar() {
    toolbarRenders += 1;
    const dispatch = useFiltersDispatch();
    return (
      <>
        <button onClick={() => dispatch({ type: 'status-changed', status: 'PAID' })}>Paid only</button>
        <button onClick={() => dispatch({ type: 'page-changed', page: 2 })}>Next page</button>
      </>
    );
  });

  it('shares the filters with every component inside the provider', async () => {
    const user = userEvent.setup();
    render(
      <FiltersProvider>
        <Toolbar />
        <Summary />
      </FiltersProvider>,
    );
    expect(screen.getByText('Showing ALL orders, page 1')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next page' }));
    expect(screen.getByText('Showing ALL orders, page 2')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Paid only' }));
    expect(screen.getByText('Showing PAID orders, page 1')).toBeTruthy();
  });

  it('does not re-render a component that only dispatches when the filters change', async () => {
    const user = userEvent.setup();
    toolbarRenders = 0;
    render(
      <FiltersProvider>
        <Toolbar />
        <Summary />
      </FiltersProvider>,
    );
    const afterMount = toolbarRenders;
    await user.click(screen.getByRole('button', { name: 'Next page' }));
    await user.click(screen.getByRole('button', { name: 'Paid only' }));
    expect(screen.getByText('Showing PAID orders, page 1')).toBeTruthy();
    expect(toolbarRenders).toBe(afterMount);
  });

  it('fails loudly when a hook is used outside the provider', () => {
    // React logs the error it rethrows; keep the test output readable.
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      expect(() => render(<Summary />)).toThrow('useFilters must be used inside <FiltersProvider>');
      expect(() => render(<Toolbar />)).toThrow('useFiltersDispatch must be used inside <FiltersProvider>');
    } finally {
      quiet.mockRestore();
    }
  });
});
