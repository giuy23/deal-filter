import { defineConfig } from 'vite';

export default defineConfig({
    root: '.',
    build: {
        outDir: 'dist',
        assetsDir: 'assets',
    },
    server: {
        host: 'localhost',
        port: 5173,
    },
});
