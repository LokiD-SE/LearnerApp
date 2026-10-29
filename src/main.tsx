import { render } from 'preact';
import { contentResult } from './content';
import { registerServiceWorker } from './pwa/register';
import { ProfilesProvider } from './store/ProfilesContext';
import { App } from './ui/App';
import './ui/styles.css';

render(
  <ProfilesProvider>
    <App content={contentResult} />
  </ProfilesProvider>,
  document.getElementById('app')!,
);

// Offline install: only in production builds - in development the worker would cache files that change.
if (import.meta.env.PROD && 'serviceWorker' in navigator) void registerServiceWorker();
