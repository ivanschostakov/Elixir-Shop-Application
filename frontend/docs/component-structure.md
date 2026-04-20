# Component Structure Convention

Use this structure for every reusable UI component and screen module.

## Goal

Keep `x.tsx` focused on rendering/composition only.
Move all non-render concerns into adjacent files.

## File Layout

For a component named `x`:

- `x.tsx`: component body only
- `x.types.ts`: props, local union types, helper type aliases
- `x.styles.ts`: `StyleSheet.create(...)` and style-only constants
- `x.const.ts`: static config/constants, breakpoints, maps, regexes
- `x.hooks.ts`: component-specific hooks and derived view logic
- `x.utils.ts`: pure helpers (formatters, mappers, parsers)

Add only what is needed; no empty files.

## Rules

- Do not declare `Props` inside `x.tsx`.
- Do not keep large constant objects/arrays/regexes inside `x.tsx`.
- Do not keep `StyleSheet.create(...)` inside `x.tsx`.
- Prefer colocated module files over global dumping grounds.
- Re-export helper functions from `x.tsx` only when used externally.

## Import Order

Inside `x.tsx`, keep imports grouped:

1. React / library imports
2. `x.*` local module imports
3. app-level imports (`@/theme`, `@/providers`, etc.)

## Migration Strategy

- Refactor by folder in small batches (for example `components/content/*` first).
- Move types/constants/styles first, then optional hooks/utils.
- Run `npm run typecheck` after each batch.
