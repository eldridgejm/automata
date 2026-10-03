# Automata Default Theme

## Automatic Tailwind CSS Rebuild

The default theme automatically rebuilds Tailwind CSS after website generation to include any custom Tailwind classes you use in your content. This feature uses a post-build hook to scan the generated HTML and regenerate the CSS with all discovered classes.

### Requirements

- **Node.js and npm** must be installed for automatic rebuilds to work.
- The first build installs Tailwind and its plugins (this directory's
  `package.json` and `package-lock.json`) with npm into
  `~/.cache/automata/tailwind/default-theme` (or under `$XDG_CACHE_HOME`), and
  again whenever they change. Later builds reuse them.
- If npm is not available, or installing or running Tailwind fails, the theme
  falls back to the pre-built CSS (checked into the repository), and logs a
  warning.

### How It Works

When you build your site:
1. The site is generated with the pre-built CSS
2. After generation completes, the post-build hook runs
3. The theme's `style.input.css` is copied next to the installed packages (so
   that its imports resolve), and the Tailwind CLI runs in the build directory,
   scanning the generated files for Tailwind classes
4. The rebuilt CSS replaces the pre-built version in the output directory

### Using Custom Tailwind Classes

You can use any Tailwind class in your content, templates, or template overrides:

```html
<div class="bg-fuchsia-500 text-white p-4 rounded-lg">
    This uses custom Tailwind classes!
</div>
```

The automatic rebuild ensures these classes are included in the final CSS, even if they weren't in the original theme.

### Fallback Behavior

If Node.js/npm is not available:
- A warning is logged: `npm not found - using pre-built Tailwind CSS`
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
- `tailwindcss` and `@tailwindcss/cli` (v4)
- `@tailwindcss/typography` (typography plugin)

### Building

Run `make` to generate the CSS:

```bash
make
```

This generates `static/static/style.css` from `style.input.css`.
