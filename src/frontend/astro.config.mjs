import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
    output: 'static',
    site: 'https://Surxe.github.io',
    base: '/',
    vite: {
        resolve: {
            preserveSymlinks: false
        }
    }
});
