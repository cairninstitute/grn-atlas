import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import React from 'react';
import Toolbar from './Toolbar';

describe('Toolbar', () => {
  it('renders numeric network statistics without treating them as arrays', () => {
    render(
      <Toolbar
        gene={{ symbol: 'AN2', name: 'ANTHOCYANIN2', species: 'petunia' }}
        stats={{ regulators: 11, targets: 75, paths: 2 }}
        cyRef={{ current: null }}
      />,
    );

    expect(screen.getByText('11')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });
});
