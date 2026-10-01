# FastAPI Vite Plugin

A Vite plugin designed to integrate seamlessly with FastAPI.

## Installation

```bash
npm install fastapi-vite-plugin --save-dev
```

## Documentation

For full documentation, please visit [https://fastapi-startkit.github.io/](https://fastapi-startkit.github.io/).

### SSR builds

Configure the server entry separately from the browser entry, then build it with Vite's SSR mode:

```ts
fastapi({
    input: "resources/js/app.tsx",
    ssr: "resources/js/ssr.tsx",
})
```

```json
{
    "scripts": {
        "build": "vite build",
        "build:ssr": "vite build --ssr resources/js/ssr.tsx"
    }
}
```

The plugin writes the server bundle to `bootstrap/ssr` by default. Set `ssrOutputDirectory` to change it. The plugin prepares the SSR build; run the generated Inertia SSR server as a separate process.

## License

The MIT License (MIT). Please see [License File](LICENSE) for more information.
