// Reference solution (frontend-state-management): the SandPay dashboard's order filters as a reducer,
// shared through two contexts - one for the state, one for the stable dispatch function.
import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react';

export type StatusFilter = 'ALL' | 'PENDING' | 'PAID' | 'FAILED';

export interface Filters {
  status: StatusFilter;
  search: string;
  page: number;
}

export type FiltersAction =
  | { type: 'status-changed'; status: StatusFilter }
  | { type: 'search-changed'; search: string }
  | { type: 'page-changed'; page: number }
  | { type: 'reset' };

export const initialFilters: Filters = { status: 'ALL', search: '', page: 1 };

function assertNever(value: never): never {
  throw new Error(`Unhandled action: ${JSON.stringify(value)}`);
}

/** Pure: never mutates `state`; returns the same object when nothing changes, so React can skip a render. */
export function filtersReducer(state: Filters, action: FiltersAction): Filters {
  switch (action.type) {
    case 'status-changed':
      if (action.status === state.status) return state;
      // A different filter gives a different list - page 3 of the old list means nothing.
      return { ...state, status: action.status, page: 1 };
    case 'search-changed': {
      const search = action.search.trim();
      if (search === state.search) return state;
      return { ...state, search, page: 1 };
    }
    case 'page-changed':
      if (!Number.isInteger(action.page) || action.page < 1 || action.page === state.page) return state;
      return { ...state, page: action.page };
    case 'reset':
      return initialFilters;
    default:
      return assertNever(action);
  }
}

const FiltersContext = createContext<Filters | null>(null);
const FiltersDispatchContext = createContext<Dispatch<FiltersAction> | null>(null);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, dispatch] = useReducer(filtersReducer, initialFilters);
  // Two contexts: components that only dispatch read the stable `dispatch` and are not re-rendered when
  // the filters change.
  return (
    <FiltersContext value={filters}>
      <FiltersDispatchContext value={dispatch}>{children}</FiltersDispatchContext>
    </FiltersContext>
  );
}

export function useFilters(): Filters {
  const filters = useContext(FiltersContext);
  if (filters === null) throw new Error('useFilters must be used inside <FiltersProvider>');
  return filters;
}

export function useFiltersDispatch(): Dispatch<FiltersAction> {
  const dispatch = useContext(FiltersDispatchContext);
  if (dispatch === null) throw new Error('useFiltersDispatch must be used inside <FiltersProvider>');
  return dispatch;
}
