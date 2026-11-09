import { copyFileSync, cpSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const staticDir = path.resolve(__dirname, 'src/bot_tv/web/static');
const distDir = path.resolve(__dirname, 'src/bot_tv/web/dist');

function copyPwaStaticAssets() {
  return {
    name: 'copy-pwa-static-assets',
    closeBundle() {
      mkdirSync(distDir, { recursive: true });
      for (const file of ['manifest.json', 'sw.js']) {
        const src = path.join(staticDir, file);
        if (existsSync(src)) {
          copyFileSync(src, path.join(distDir, file));
        }
      }
      const iconsSrc = path.join(staticDir, 'icons');
      if (existsSync(iconsSrc)) {
        cpSync(iconsSrc, path.join(distDir, 'icons'), { recursive: true });
      }
    },
  };
}

export default defineConfig({
  root: staticDir,
  base: '/static/',
  publicDir: false,
  plugins: [copyPwaStaticAssets()],
  resolve: {
    alias: {
      '/static': staticDir,
      'preact-setup': path.join(staticDir, 'lib/preact-setup.js'),
      'lib/utils': path.join(staticDir, 'lib/utils.js'),
      'lib/a11y': path.join(staticDir, 'lib/a11y.js'),
      'chart.js': 'chart.js/auto',
    },
  },
  build: {
    outDir: distDir,
    emptyOutDir: true,
    target: 'es2022',
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/chart.js')) {
            return 'chart';
          }
          if (id.includes('node_modules/preact') || id.includes('node_modules/htm')) {
            return 'framework';
          }
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8080',
        ws: true,
      },
    },
  },
});
