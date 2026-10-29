import { render } from 'preact';
import { contentResult } from './content';
import { registerServiceWorker } from './pwa/register';
import { ProgressProvider } from './store/ProgressContext';
import { App } from './ui/App';
import './ui/styles.css';

render(
  <ProgressProvider>
    <App content={contentResult} />
  </ProgressProvider>,
  document.getElementById('app')!,
);

// Offline install: only in production builds - in development the worker would cache files that change.
if (import.meta.env.PROD && 'serviceWorker' in navigator) void registerServiceWorker();
