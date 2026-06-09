import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TaskTeamWarning } from '../TaskTeamWarning';

describe('TaskTeamWarning', () => {
  it('renders warning text when off-project teams exist', () => {
    render(<TaskTeamWarning offProjectTeamNames={['SEO', 'Ops']} />);
    expect(screen.getByTestId('task-team-warning')).toBeInTheDocument();
    expect(screen.getByText(/SEO, Ops/)).toBeInTheDocument();
  });

  it('renders nothing when there are no off-project teams', () => {
    const { container } = render(<TaskTeamWarning offProjectTeamNames={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
