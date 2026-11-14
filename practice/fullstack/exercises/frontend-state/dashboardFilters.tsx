// Exercise (frontend-state-management): the SandPay dashboard's order filters as a reducer shared through
// context. It "works" in the happy path, but the reducer mutates state and forgets rules, the hooks
// silently return nothing outside the provider, and every filter change re-renders components that only
// dispatch. Make every test in tests/frontend-state/dashboard-filters.test.tsx pass.
// Keep the exported names and types.
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

export function filtersReducer(state: Filters, action: FiltersAction): Filters {
  switch (action.type) {
    case 'status-changed':
      state.status = action.status;
      return { ...state };
    case 'search-changed':
      return { ...state, search: action.search };
    case 'page-changed':
      return { ...state, page: action.page };
    default:
      return state;
  }
}

const FiltersContext = createContext<{ filters: Filters; dispatch: Dispatch<FiltersAction> } | undefined>(
  undefined,
);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, dispatch] = useReducer(filtersReducer, initialFilters);
  return <FiltersContext value={{ filters, dispatch }}>{children}</FiltersContext>;
}

export function useFilters(): Filters {
  return useContext(FiltersContext)?.filters as Filters;
}

export function useFiltersDispatch(): Dispatch<FiltersAction> {
  return useContext(FiltersContext)?.dispatch as Dispatch<FiltersAction>;
}
