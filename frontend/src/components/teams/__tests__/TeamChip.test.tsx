import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TeamChip } from '../TeamChip';

describe('TeamChip', () => {
  it('renders team name', () => {
    render(<TeamChip team={{ id: 1, name: 'SEO', color: '#10B981' }} />);
    expect(screen.getByText('SEO')).toBeInTheDocument();
  });
});
