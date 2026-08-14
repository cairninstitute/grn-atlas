import React, { createContext, useContext, useMemo, useReducer } from 'react';
import { initialResearchSession, researchSessionReducer } from './researchSessionReducer';

const ResearchSessionContext = createContext(null);

export function ResearchSessionProvider({ children }) {
  const [state, dispatch] = useReducer(researchSessionReducer, initialResearchSession);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return (
    <ResearchSessionContext.Provider value={value}>
      {children}
    </ResearchSessionContext.Provider>
  );
}

export function useResearchSession() {
  const ctx = useContext(ResearchSessionContext);
  if (!ctx) {
    throw new Error('useResearchSession must be used within a ResearchSessionProvider');
  }
  return ctx;
}
