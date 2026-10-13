import { describe, expect, it } from 'vitest';
import { getLayout } from './NetworkVisualization';


describe('getLayout', () => {
  it('provides a label-aware circle layout for small feedback circuits', () => {
    const layout = getLayout('circle');

    expect(layout.name).toBe('circle');
    expect(layout.avoidOverlap).toBe(true);
    expect(layout.nodeDimensionsIncludeLabels).toBe(true);
    expect(layout.spacingFactor).toBeGreaterThan(1);
  });

  it('provides a force-directed layout for larger subgraphs', () => {
    const layout = getLayout('cose');

    expect(layout.name).toBe('cose');
    expect(layout.nodeDimensionsIncludeLabels).toBe(true);
    expect(layout.idealEdgeLength).toBeGreaterThanOrEqual(100);
  });

  it('falls back to preset only for unknown layout names', () => {
    expect(getLayout('not-a-layout')).toEqual({ name: 'preset' });
  });
});
