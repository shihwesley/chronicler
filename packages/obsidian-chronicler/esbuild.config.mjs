import esbuild from 'esbuild';

const isProduction = process.argv[2] === 'production';

esbuild.build({
  entryPoints: ['src/main.ts'],
  bundle: true,
  external: ['obsidian', 'electron', '@codemirror/*', '@lezer/*', 'child_process'],
  format: 'cjs',
  target: 'ES6',
  outfile: 'main.js',
  sourcemap: isProduction ? false : 'inline',
  minify: isProduction,
}).catch(() => process.exit(1));
