import React, { useState, useRef, useEffect } from 'react';
import '../styles/Toolbar.css';

export default function Toolbar({ gene, stats, cyRef }) {
  const [showExport, setShowExport] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowExport(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!gene) return null;

  const regulatorCount = stats?.regulators?.length || 0;
  const targetCount = stats?.targets?.length || 0;
  const pathCount = stats?.paths?.length || 0;

  const download = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    setShowExport(false);
  };

  const exportPNG = () => {
    const cy = cyRef?.current;
    if (!cy) return;
    const dataUrl = cy.png({ full: true, scale: 2, bg: '#1a1a1a' });
    fetch(dataUrl).then(r => r.blob()).then(blob => {
      download(blob, `grn_atlas_${gene.symbol}.png`);
    });
  };

  const exportSVG = () => {
    const cy = cyRef?.current;
    if (!cy) return;
    const svgContent = cy.svg({ full: true, scale: 1, bg: '#1a1a1a' });
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    download(blob, `grn_atlas_${gene.symbol}.svg`);
  };

  const exportJSON = () => {
    const cy = cyRef?.current;
    if (!cy) return;
    const json = cy.json();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    download(blob, `grn_atlas_${gene.symbol}.json`);
  };

  const exportCSV = () => {
    const cy = cyRef?.current;
    if (!cy) return;
    const rows = ['source,target,regulation_type,confidence,sources'];
    cy.edges().forEach(edge => {
      const d = edge.data();
      rows.push([
        edge.source().data('label'),
        edge.target().data('label'),
        d.regulation_type || '',
        d.confidence || '',
        (d.source_databases || []).join(';')
      ].join(','));
    });
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    download(blob, `grn_atlas_${gene.symbol}.csv`);
  };

  const hasCy = !!cyRef?.current;

  return (
    <div className="toolbar">
      <div className="toolbar-gene-info">
        <h2 className="gene-symbol">{gene.symbol}</h2>
        <span className="gene-name">{gene.name}</span>
      </div>

      <div className="toolbar-badges">
        <div className="badge">
          <span className="badge-label">Species</span>
          <span className="badge-value">{gene.species}</span>
        </div>
        {gene.is_tf && (
          <div className="badge tf-badge">
            <span className="badge-label">Type</span>
            <span className="badge-value">Transcription Factor</span>
          </div>
        )}
      </div>

      <div className="toolbar-stats">
        <div className="stat-item">
          <span className="stat-label">Regulators</span>
          <span className="stat-value">{regulatorCount}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Targets</span>
          <span className="stat-value">{targetCount}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Paths</span>
          <span className="stat-value">{pathCount}</span>
        </div>
      </div>

      <div className="toolbar-actions">
        <div className="export-wrapper" ref={dropdownRef}>
          <button className="action-button" title="Export network"
            onClick={() => setShowExport(!showExport)}>
            Export
          </button>
          {showExport && (
            <div className="export-dropdown">
              <button className="export-option" onClick={exportPNG} disabled={!hasCy}>
                <span className="export-icon">PNG</span>
                <span className="export-desc">High-res image</span>
              </button>
              <button className="export-option" onClick={exportSVG} disabled={!hasCy}>
                <span className="export-icon">SVG</span>
                <span className="export-desc">Vector graphic</span>
              </button>
              <button className="export-option" onClick={exportJSON} disabled={!hasCy}>
                <span className="export-icon">JSON</span>
                <span className="export-desc">Cytoscape data</span>
              </button>
              <button className="export-option" onClick={exportCSV} disabled={!hasCy}>
                <span className="export-icon">CSV</span>
                <span className="export-desc">Edge list</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
