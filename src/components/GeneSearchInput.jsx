import React, { useState, useEffect, useRef } from 'react';
import { geneAPI } from '../services/apiService';
import { geneLabel } from '../utils/geneLabel';

// Debounced gene autocomplete. Resolves symbols/synonyms/ids for a species.
// value/onChange keep the raw text in the parent; onSelect(gene) fires on pick.
export default function GeneSearchInput({ value, onChange, onSelect, species, placeholder, style }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const timer = useRef(null);
  const box = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const query = (q) => {
    clearTimeout(timer.current);
    if (!q || q.length < 2) { setSuggestions([]); setOpen(false); return; }
    timer.current = setTimeout(async () => {
      try {
        const d = await geneAPI.search(q, 8, species);
        setSuggestions(d.results || []);
        setOpen((d.results || []).length > 0);
        setActive(-1);
      } catch { /* ignore */ }
    }, 200);
  };

  const pick = (g) => {
    onChange(geneLabel(g).label);
    if (onSelect) onSelect(g);
    setOpen(false);
  };

  const onKey = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(suggestions[active]); }
    else if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div ref={box} style={{ position: 'relative', ...style }}>
      <input
        className="gs-input" style={{ width: '100%', boxSizing: 'border-box' }}
        placeholder={placeholder} value={value}
        onChange={(e) => { onChange(e.target.value); query(e.target.value); }}
        onFocus={() => value && value.length >= 2 && query(value)}
        onKeyDown={onKey}
      />
      {open && (
        <ul className="gene-suggest">
          {suggestions.map((g, i) => {
            const gl = geneLabel(g);
            return (
              <li key={g.id} className={i === active ? 'active' : ''}
                  onMouseDown={() => pick(g)} onMouseEnter={() => setActive(i)}>
                <strong>{gl.label}</strong>
                {gl.inferred && <span className="gs-ns" title="inferred from ortholog">°</span>}
                {g.is_tf && <span className="gs-ns"> TF</span>}
                {gl.label !== g.id && <span className="gene-suggest-name"> · {g.id}</span>}
                {g.name && <span className="gene-suggest-name"> — {g.name.slice(0, 40)}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
