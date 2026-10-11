// Content files are YAML; the Vite plugin in vite.config.ts turns each one into a JS module.
declare module '*.yaml' {
  const data: unknown;
  export default data;
}
