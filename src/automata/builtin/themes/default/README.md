# Automata Default Theme

## Automatic Tailwind CSS Rebuild

The default theme automatically rebuilds Tailwind CSS after website generation to include any custom Tailwind classes you use in your content. This feature uses a post-build hook to scan the generated HTML and regenerate the CSS with all discovered classes.

### Requirements

- **Node.js and npx** must be installed for automatic rebuilds to work
- If Node.js is not available, the theme will fall back to using the pre-built CSS (checked into the repository)
- A warning will be logged if npx is not found

### How It Works

When you generate your site:
1. The site is generated with the pre-built CSS
2. After generation completes, the post-build hook runs
3. The hook scans all HTML files in the build directory for Tailwind classes
4. Tailwind CLI rebuilds the CSS to include all discovered classes
5. The rebuilt CSS replaces the pre-built version in the output directory

### Using Custom Tailwind Classes

You can use any Tailwind class in your content, templates, or template overrides:

```html
<div class="bg-fuchsia-500 text-white p-4 rounded-lg">
    This uses custom Tailwind classes!
</div>
```

The automatic rebuild ensures these classes are included in the final CSS, even if they weren't in the original theme.

### Fallback Behavior

If Node.js/npx is not available:
- A warning is logged: `npx not found - using pre-built Tailwind CSS`
- The pre-built CSS (checked into the repository) is used
- Site generation continues normally
- Your site will work, but custom Tailwind classes may not be styled

## Manual Building (Theme Development)

For theme development, you can manually rebuild the CSS:

### Installation

Install Node.js and the required dependencies:

```bash
npm install
```

This installs:
- `tailwindcss` (v4.1.18)
- `@tailwindcss/typography` (typography plugin)

### Building

Run `make` to generate the CSS:

```bash
make
```

This generates `static/static/style.css` from `style.input.css`.
