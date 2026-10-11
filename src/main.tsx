import { render } from 'preact';
import { contentResult } from './content';
import { ProgressProvider } from './store/ProgressContext';
import { App } from './ui/App';
import './ui/styles.css';

render(
  <ProgressProvider>
    <App content={contentResult} />
  </ProgressProvider>,
  document.getElementById('app')!,
);
