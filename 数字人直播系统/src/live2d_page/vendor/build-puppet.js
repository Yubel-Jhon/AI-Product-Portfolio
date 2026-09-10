import { build } from 'esbuild'
await build({
  entryPoints: ['puppet-entry.js'],
  bundle: true,
  format: 'esm',
  outfile: 'puppet.bundle.mjs',
  minify: false,
  logLevel: 'info',
})
console.log('puppet.bundle.mjs 构建完成')
