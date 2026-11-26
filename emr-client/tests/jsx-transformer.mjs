import { transformSync } from 'esbuild';

export default {
  process(sourceText, sourcePath) {
    const result = transformSync(sourceText, {
      loader: 'jsx',
      format: 'esm',
      jsx: 'automatic',
      sourcefile: sourcePath,
      sourcemap: 'inline',
    });
    return { code: result.code };
  },
};
