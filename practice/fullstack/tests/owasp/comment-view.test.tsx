// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { CommentView, safeHref } from '../../exercises/owasp/CommentView.js';

describe('safeHref', { tags: ['@exercise'] }, () => {
  test.each([
    ['https://shop.sandpay.example/help', 'https://shop.sandpay.example/help'],
    ['http://books.example/catalogue', 'http://books.example/catalogue'],
    ['mailto:asha@example.test', 'mailto:asha@example.test'],
    ['/orders/101', '/orders/101'],
  ])('accepts %s', (raw, expected) => {
    expect(safeHref(raw)).toBe(expected);
  });

  test.each([
    'javascript:alert(1)',
    '  JaVaScRiPt:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    '//evil.example/login',
    'evil.example',
    '',
  ])('rejects %s', (raw) => {
    expect(safeHref(raw)).toBeUndefined();
  });
});

describe('CommentView', { tags: ['@exercise'] }, () => {
  test('markup in the comment is shown as text and never becomes elements', () => {
    const { container } = render(
      <CommentView
        comment={{ author: '<b>Meera</b>', text: 'Arrived late <img src="x" onerror="alert(1)">' }}
      />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('b')).toBeNull();
    expect(screen.getByText('Arrived late <img src="x" onerror="alert(1)">')).toBeTruthy();
    expect(screen.getByText('<b>Meera</b>')).toBeTruthy();
  });

  test('line breaks in the text are kept with CSS, not with <br> markup', () => {
    render(<CommentView comment={{ author: 'Meera', text: 'Line one\nLine two' }} />);
    const text = screen.getByText(/Line one/);
    expect(text.textContent).toBe('Line one\nLine two');
    expect(getComputedStyle(text).whiteSpace).toBe('pre-line');
  });

  test('a safe website becomes a link marked as user content', () => {
    render(<CommentView comment={{ author: 'Meera', text: 'Thanks', website: 'https://meera.example/' }} />);
    const link = screen.getByRole('link', { name: 'Website' });
    expect(link.getAttribute('href')).toBe('https://meera.example/');
    expect(link.getAttribute('rel')?.split(' ')).toEqual(
      expect.arrayContaining(['nofollow', 'ugc', 'noopener', 'noreferrer']),
    );
  });

  test('an unsafe website is not rendered as a link at all', () => {
    render(
      <CommentView
        comment={{ author: 'Meera', text: 'Thanks', website: 'data:text/html,<script>alert(1)</script>' }}
      />,
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText('Thanks')).toBeTruthy();
  });
});
